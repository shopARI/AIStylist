#!/usr/bin/env python3
"""
SAM3 Product Image Segmentation Pipeline
- Connects to Neo4j to fetch product images
- Downloads images from URLs
- Processes with SAM3 for segmentation
- Saves masks, scores, and all SAM3 outputs
"""

import os
import sys
import json
import torch
import asyncio
import requests
import numpy as np
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from PIL import Image
from io import BytesIO

# Neo4j imports
from neo4j import GraphDatabase, AsyncGraphDatabase
from dotenv import load_dotenv

# SAM3 imports
from sam3.model_builder import build_sam3_image_model
from sam3.model.sam3_image_processor import Sam3Processor as Sam3ImageProcessor

# Configure paths
PROJECT_ROOT = Path("/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27")
OUTPUT_ROOT = Path("/home/leo/sam3_product_outputs")
IMAGES_DIR = OUTPUT_ROOT / "images"
MASKS_DIR = OUTPUT_ROOT / "masks"
RESULTS_DIR = OUTPUT_ROOT / "results"
METADATA_DIR = OUTPUT_ROOT / "metadata"

# Create output directories
for dir_path in [OUTPUT_ROOT, IMAGES_DIR, MASKS_DIR, RESULTS_DIR, METADATA_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env")

# Neo4j configuration
NEO4J_URI = os.getenv("NEO4J_URL", "neo4j://34.135.40.119:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
# Use 'neo4j' database which has full HTTP URLs (not relative paths)
NEO4J_DATABASE = os.getenv("SAM3_NEO4J_DATABASE", "neo4j")

print("="*80)
print("SAM3 Product Image Segmentation Pipeline")
print("="*80)
print(f"Output directory: {OUTPUT_ROOT}")
print(f"Neo4j URI: {NEO4J_URI}")
print(f"Neo4j Database: {NEO4J_DATABASE}")
print("="*80)


class Neo4jConnection:
    """Neo4j database connection handler"""

    def __init__(self, uri: str, user: str, password: str, database: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def close(self):
        if self.driver:
            self.driver.close()

    def query_products_with_images(self, limit: int = 10, category_filter: str = None) -> List[Dict[str, Any]]:
        """
        Query products that have image URLs (full HTTP URLs only)

        Args:
            limit: Number of products to return
            category_filter: Optional category filter (e.g., 'shirt', 'dress', 'suit')
        """
        if category_filter:
            query = f"""
            MATCH (p:Product)
            WHERE p.images IS NOT NULL
            AND p.images CONTAINS 'http'
            AND (toLower(p.title) CONTAINS $filter OR toLower(p.category) CONTAINS $filter)
            RETURN p.id AS product_id,
                   p.title AS title,
                   p.images AS images,
                   p.category AS category,
                   p.brand AS brand,
                   p.price AS price,
                   p.description AS description
            LIMIT $limit
            """
            params = {"limit": limit, "filter": category_filter.lower()}
        else:
            query = """
            MATCH (p:Product)
            WHERE p.images IS NOT NULL
            AND p.images CONTAINS 'http'
            RETURN p.id AS product_id,
                   p.title AS title,
                   p.images AS images,
                   p.category AS category,
                   p.brand AS brand,
                   p.price AS price,
                   p.description AS description
            LIMIT $limit
            """
            params = {"limit": limit}

        with self.driver.session(database=self.database) as session:
            result = session.run(query, params)
            products = []
            for record in result:
                # Parse images JSON string
                images_str = record["images"]
                try:
                    images_list = json.loads(images_str) if images_str else []
                    # Use first image if available
                    image_url = images_list[0] if images_list else None
                except (json.JSONDecodeError, IndexError):
                    image_url = None

                if image_url:  # Only add products with valid image URLs
                    products.append({
                        "product_id": record["product_id"],
                        "title": record["title"],
                        "image_url": image_url,
                        "images_all": images_list,
                        "category": record.get("category"),
                        "brand": record.get("brand"),
                        "price": record.get("price"),
                        "description": record.get("description")
                    })
            return products


class SAM3Processor:
    """SAM3 model processor for segmentation"""

    def __init__(self):
        print("\n[SAM3] Loading model...")
        self.model = build_sam3_image_model()
        self.processor = Sam3ImageProcessor(self.model)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[SAM3] Model loaded on {self.device}")

    def segment_image(
        self,
        image: Image.Image,
        text_prompts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Segment image with SAM3 and return ALL available outputs

        Args:
            image: PIL Image
            text_prompts: Optional list of text prompts (e.g., ["clothing", "dress", "shirt"])

        Returns:
            Dictionary with masks, scores, boxes, vision features, and ALL SAM3 outputs
        """
        if text_prompts is None:
            # Default prompts for fashion products
            text_prompts = ["clothing", "garment", "product"]

        all_masks = []
        all_boxes = []
        all_scores = []
        all_masks_logits = []

        # Step 1: Set image (do this once to extract backbone features)
        inference_state = self.processor.set_image(image)

        # Extract backbone features (these are constant for the image)
        vision_features = None
        vision_pos_enc = None
        backbone_fpn = None

        if "backbone_out" in inference_state:
            backbone_out = inference_state["backbone_out"]

            # Extract vision features (256-dim embeddings at 72x72)
            if "vision_features" in backbone_out and torch.is_tensor(backbone_out["vision_features"]):
                vision_features = backbone_out["vision_features"].cpu().numpy()

            # Extract position encodings
            if "vision_pos_enc" in backbone_out:
                vision_pos_enc_list = backbone_out["vision_pos_enc"]
                if isinstance(vision_pos_enc_list, list):
                    vision_pos_enc = [v.cpu().numpy() if torch.is_tensor(v) else v for v in vision_pos_enc_list]

            # Extract FPN features (Feature Pyramid Network - multi-scale features)
            if "backbone_fpn" in backbone_out:
                fpn_list = backbone_out["backbone_fpn"]
                if isinstance(fpn_list, list):
                    backbone_fpn = [f.cpu().numpy() if torch.is_tensor(f) else f for f in fpn_list]

        # Step 2: Process each text prompt
        for prompt in text_prompts:
            # Set text prompt (reuses the same inference_state)
            output = self.processor.set_text_prompt(state=inference_state, prompt=prompt)

            # Step 3: Extract results
            masks = output["masks"]
            boxes = output["boxes"]
            scores = output["scores"]
            masks_logits = output.get("masks_logits", None)

            # Convert to numpy if tensors
            if torch.is_tensor(masks):
                masks = masks.cpu().numpy()
            if torch.is_tensor(boxes):
                boxes = boxes.cpu().numpy()
            if torch.is_tensor(scores):
                scores = scores.cpu().numpy()
            if masks_logits is not None and torch.is_tensor(masks_logits):
                masks_logits = masks_logits.cpu().numpy()

            all_masks.append(masks)
            all_boxes.append(boxes)
            all_scores.append(scores)
            if masks_logits is not None:
                all_masks_logits.append(masks_logits)

        # Combine results from all prompts
        combined_masks = np.concatenate(all_masks, axis=0) if all_masks else np.array([])
        combined_boxes = np.concatenate(all_boxes, axis=0) if all_boxes else np.array([])
        combined_scores = np.concatenate(all_scores, axis=0) if all_scores else np.array([])
        combined_masks_logits = np.concatenate(all_masks_logits, axis=0) if all_masks_logits else np.array([])

        # Extract all outputs
        results = {
            # Segmentation outputs
            "masks": combined_masks,
            "boxes": combined_boxes,
            "iou_scores": combined_scores,
            "masks_logits": combined_masks_logits,
            "image_size": image.size,
            "num_masks": len(combined_masks) if len(combined_masks) > 0 else 0,
            "text_prompts": text_prompts,

            # Vision backbone features
            "vision_features": vision_features,  # Shape: [1, 256, H/16, W/16] - high-level features
            "vision_pos_enc": vision_pos_enc,    # Position encodings
            "backbone_fpn": backbone_fpn,        # Multi-scale FPN features
        }

        return results


class ProductKeywordExtractor:
    """Extract product-specific keywords for SAM3 prompts"""

    # Fashion product keywords to look for
    FASHION_KEYWORDS = [
        # Clothing
        'dress', 'shirt', 'blouse', 'top', 'sweater', 'hoodie', 'jacket', 'coat',
        'jeans', 'pants', 'trousers', 'shorts', 'skirt', 'suit', 'blazer',
        'cardigan', 'vest', 'turtleneck', 't-shirt', 'polo', 'sweatshirt',
        # Footwear
        'shoes', 'sneakers', 'boots', 'sandals', 'heels', 'flats', 'loafers',
        'sneaker', 'boot', 'sandal',
        # Accessories
        'sunglasses', 'glasses', 'eyewear', 'bag', 'purse', 'wallet', 'belt',
        'scarf', 'hat', 'cap', 'gloves', 'watch', 'jewelry', 'earrings',
        'necklace', 'bracelet', 'ring',
        # Generic fallbacks
        'clothing', 'garment', 'apparel', 'fashion', 'wear'
    ]

    @staticmethod
    def extract_keywords(title: str, description: str = None) -> List[str]:
        """
        Extract product keywords from title and description

        Args:
            title: Product title
            description: Product description (optional)

        Returns:
            List of extracted keywords (most specific first)
        """
        text = (title + " " + (description or "")).lower()

        # Find all matching keywords
        found_keywords = []
        for keyword in ProductKeywordExtractor.FASHION_KEYWORDS:
            if keyword in text:
                found_keywords.append(keyword)

        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in found_keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        # If no keywords found, use generic fallbacks
        if not unique_keywords:
            unique_keywords = ['clothing', 'product', 'item']

        # Limit to top 4 keywords
        return unique_keywords[:4]


class ImageDownloader:
    """Download and validate product images"""

    @staticmethod
    def download_image(url: str, timeout: int = 10) -> Optional[Image.Image]:
        """Download image from URL"""
        try:
            response = requests.get(url, timeout=timeout, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            return image
        except Exception as e:
            print(f"[ERROR] Failed to download image from {url}: {e}")
            return None

    @staticmethod
    def save_image(image: Image.Image, filepath: Path):
        """Save image to disk"""
        image.save(filepath, format='PNG')


class ResultSaver:
    """Save SAM3 segmentation results"""

    @staticmethod
    def save_masks(masks: np.ndarray, product_id: str, output_dir: Path):
        """Save individual masks as images"""
        mask_files = []
        for idx, mask in enumerate(masks):
            mask_file = output_dir / f"{product_id}_mask_{idx}.png"

            # Squeeze to 2D if needed (remove single dimensions)
            mask_2d = np.squeeze(mask)

            # Ensure it's 2D
            if mask_2d.ndim != 2:
                print(f"  [WARNING] Unexpected mask shape: {mask.shape}, squeezed to {mask_2d.shape}")
                # Take first channel if still 3D
                if mask_2d.ndim == 3:
                    mask_2d = mask_2d[0]

            # Convert boolean mask to image
            mask_img = Image.fromarray((mask_2d * 255).astype(np.uint8))
            mask_img.save(mask_file)
            mask_files.append(str(mask_file))
        return mask_files

    @staticmethod
    def save_overlay(
        image: Image.Image,
        masks: np.ndarray,
        scores: np.ndarray,
        product_id: str,
        output_dir: Path
    ):
        """Save visualization with masks overlaid on original image"""
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, min(3, len(masks)) + 1, figsize=(20, 5))
        if len(masks) == 0:
            axes = [axes]

        # Original image
        axes[0].imshow(image)
        axes[0].set_title('Original Image')
        axes[0].axis('off')

        # Masks
        for idx, (mask, score) in enumerate(zip(masks[:3], scores[:3])):
            if idx + 1 < len(axes):
                # Squeeze mask to 2D
                mask_2d = np.squeeze(mask)
                if mask_2d.ndim == 3:
                    mask_2d = mask_2d[0]

                axes[idx + 1].imshow(image)
                axes[idx + 1].imshow(mask_2d, alpha=0.5, cmap='jet')
                axes[idx + 1].set_title(f'Mask {idx+1} (Score: {score:.3f})')
                axes[idx + 1].axis('off')

        overlay_file = output_dir / f"{product_id}_overlay.png"
        plt.tight_layout()
        plt.savefig(overlay_file, dpi=150, bbox_inches='tight')
        plt.close()

        return str(overlay_file)

    @staticmethod
    def save_metadata(
        product_info: Dict[str, Any],
        sam3_results: Dict[str, Any],
        mask_files: List[str],
        overlay_file: str,
        feature_files: Dict[str, str],
        output_dir: Path
    ):
        """Save comprehensive metadata as JSON"""

        # Build feature shapes dict
        feature_shapes = {}
        if sam3_results.get("vision_features") is not None:
            feature_shapes["vision_features"] = list(sam3_results["vision_features"].shape)
        if sam3_results.get("vision_pos_enc") is not None:
            feature_shapes["vision_pos_enc"] = [
                list(p.shape) if hasattr(p, 'shape') else str(type(p))
                for p in sam3_results["vision_pos_enc"]
            ]
        if sam3_results.get("backbone_fpn") is not None:
            feature_shapes["backbone_fpn"] = [
                list(fpn.shape) if hasattr(fpn, 'shape') else str(type(fpn))
                for fpn in sam3_results["backbone_fpn"]
            ]
        if sam3_results.get("masks_logits") is not None and len(sam3_results["masks_logits"]) > 0:
            feature_shapes["masks_logits"] = list(sam3_results["masks_logits"].shape)

        metadata = {
            "product_info": product_info,
            "segmentation_results": {
                "num_masks": sam3_results["num_masks"],
                "image_size": sam3_results["image_size"],
                "text_prompts": sam3_results["text_prompts"],
                "iou_scores": sam3_results["iou_scores"].tolist() if len(sam3_results["iou_scores"]) > 0 else [],
                "mask_files": mask_files,
                "overlay_file": overlay_file
            },
            "sam3_features": {
                "feature_files": feature_files,
                "feature_shapes": feature_shapes,
                "description": {
                    "vision_features": "High-level 256-dim vision features at 1/16 resolution",
                    "vision_pos_enc": "Positional encodings for vision features",
                    "backbone_fpn": "Feature Pyramid Network features at multiple scales",
                    "masks_logits": "Raw mask logits before sigmoid activation"
                }
            },
            "timestamp": datetime.now().isoformat(),
            "model": "facebook/sam3"
        }

        metadata_file = output_dir / f"{product_info['product_id']}_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        return str(metadata_file)

    @staticmethod
    def save_embeddings(
        sam3_results: Dict[str, Any],
        product_id: str,
        output_dir: Path
    ):
        """Save ALL SAM3 features as .npy files for later inspection"""
        feature_files = {}

        # Save vision features (256-dim at 72x72)
        if sam3_results.get("vision_features") is not None:
            feat_file = output_dir / f"{product_id}_vision_features.npy"
            np.save(feat_file, sam3_results["vision_features"])
            feature_files["vision_features"] = str(feat_file)
            print(f"    • Vision features shape: {sam3_results['vision_features'].shape}")

        # Save position encodings (save as pickle due to variable shapes)
        if sam3_results.get("vision_pos_enc") is not None:
            import pickle
            pos_file = output_dir / f"{product_id}_vision_pos_enc.pkl"
            with open(pos_file, 'wb') as f:
                pickle.dump(sam3_results["vision_pos_enc"], f)
            feature_files["vision_pos_enc"] = str(pos_file)
            print(f"    • Position encodings: {len(sam3_results['vision_pos_enc'])} levels")
            for i, pos in enumerate(sam3_results["vision_pos_enc"]):
                print(f"      - Level {i}: {pos.shape}")

        # Save FPN features (multi-scale, save as pickle due to variable shapes)
        if sam3_results.get("backbone_fpn") is not None:
            import pickle
            fpn_file = output_dir / f"{product_id}_backbone_fpn.pkl"
            with open(fpn_file, 'wb') as f:
                pickle.dump(sam3_results["backbone_fpn"], f)
            feature_files["backbone_fpn"] = str(fpn_file)
            print(f"    • FPN features: {len(sam3_results['backbone_fpn'])} scales")
            for i, fpn in enumerate(sam3_results["backbone_fpn"]):
                print(f"      - Scale {i}: {fpn.shape}")

        # Save mask logits (raw probabilities)
        if sam3_results.get("masks_logits") is not None and len(sam3_results["masks_logits"]) > 0:
            logits_file = output_dir / f"{product_id}_masks_logits.npy"
            np.save(logits_file, sam3_results["masks_logits"])
            feature_files["masks_logits"] = str(logits_file)
            print(f"    • Mask logits shape: {sam3_results['masks_logits'].shape}")

        return feature_files


async def main():
    """Main pipeline execution"""

    # Configuration
    NUM_PRODUCTS = int(os.getenv("NUM_PRODUCTS", "10"))  # Number of products to process
    CATEGORY_FILTER = os.getenv("CATEGORY_FILTER", None)  # Optional category filter

    if CATEGORY_FILTER:
        print(f"\n[CONFIG] Processing {NUM_PRODUCTS} products (filtering for: {CATEGORY_FILTER})")
    else:
        print(f"\n[CONFIG] Processing {NUM_PRODUCTS} products")

    # Step 1: Connect to Neo4j
    print("\n[1/5] Connecting to Neo4j...")
    neo4j_conn = Neo4jConnection(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE)

    try:
        # Step 2: Query products with images
        print(f"[2/5] Querying {NUM_PRODUCTS} products with images...")
        products = neo4j_conn.query_products_with_images(limit=NUM_PRODUCTS, category_filter=CATEGORY_FILTER)
        print(f"✓ Found {len(products)} products with images")

        if not products:
            print("[ERROR] No products with images found!")
            return

        # Step 3: Initialize SAM3
        print("\n[3/5] Initializing SAM3 model...")
        sam3_processor = SAM3Processor()

        # Step 4: Process each product
        print(f"\n[4/5] Processing {len(products)} products...")
        downloader = ImageDownloader()
        saver = ResultSaver()

        processed_count = 0
        failed_count = 0

        for idx, product in enumerate(products, 1):
            product_id = product["product_id"]
            image_url = product["image_url"]

            print(f"\n--- Product {idx}/{len(products)}: {product_id} ---")
            print(f"Title: {product['title']}")
            print(f"URL: {image_url}")

            # Download image
            print("  • Downloading image...")
            image = downloader.download_image(image_url)

            if image is None:
                print("  ✗ Failed to download image")
                failed_count += 1
                continue

            # Save original image
            image_file = IMAGES_DIR / f"{product_id}.png"
            downloader.save_image(image, image_file)
            print(f"  ✓ Saved to {image_file}")

            # Extract keywords from product title/description
            keywords = ProductKeywordExtractor.extract_keywords(
                product['title'],
                product.get('description')
            )
            print(f"  • Extracted keywords: {keywords}")

            # Segment with SAM3 using extracted keywords
            print("  • Running SAM3 segmentation...")
            sam3_results = sam3_processor.segment_image(
                image,
                text_prompts=keywords
            )
            print(f"  ✓ Generated {sam3_results['num_masks']} masks")
            print(f"  ✓ IoU scores: {sam3_results['iou_scores']}")

            # Save masks
            print("  • Saving masks...")
            mask_files = saver.save_masks(
                sam3_results["masks"],
                product_id,
                MASKS_DIR
            )
            print(f"  ✓ Saved {len(mask_files)} mask files")

            # Save overlay visualization
            print("  • Creating overlay visualization...")
            overlay_file = saver.save_overlay(
                image,
                sam3_results["masks"],
                sam3_results["iou_scores"],
                product_id,
                RESULTS_DIR
            )
            print(f"  ✓ Saved overlay to {overlay_file}")

            # Save all SAM3 features
            print("  • Saving SAM3 features...")
            feature_files = saver.save_embeddings(
                sam3_results,
                product_id,
                RESULTS_DIR
            )
            if feature_files:
                print(f"  ✓ Saved {len(feature_files)} feature files")

            # Save metadata
            print("  • Saving metadata...")
            metadata_file = saver.save_metadata(
                product,
                sam3_results,
                mask_files,
                overlay_file,
                feature_files,
                METADATA_DIR
            )
            print(f"  ✓ Saved metadata to {metadata_file}")

            processed_count += 1

        # Step 5: Summary
        print("\n" + "="*80)
        print("[5/5] PIPELINE COMPLETE")
        print("="*80)
        print(f"✓ Successfully processed: {processed_count}/{len(products)}")
        print(f"✗ Failed: {failed_count}/{len(products)}")
        print(f"\nOutput directories:")
        print(f"  • Images:   {IMAGES_DIR}")
        print(f"  • Masks:    {MASKS_DIR}")
        print(f"  • Results:  {RESULTS_DIR}")
        print(f"  • Metadata: {METADATA_DIR}")
        print("="*80)

    finally:
        neo4j_conn.close()
        print("\n✓ Neo4j connection closed")


if __name__ == "__main__":
    asyncio.run(main())
