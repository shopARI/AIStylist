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
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from PIL import Image
from io import BytesIO

# Neo4j imports
from neo4j import GraphDatabase, AsyncGraphDatabase
from dotenv import load_dotenv

# SAM3 imports
from transformers import Sam3Model, Sam3Processor

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
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "productionbackup2")

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

    def query_products_with_images(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Query products that have image URLs
        """
        query = """
        MATCH (p:Product)
        WHERE p.image_url IS NOT NULL
        RETURN p.id AS product_id,
               p.title AS title,
               p.image_url AS image_url,
               p.category AS category,
               p.brand AS brand,
               p.price AS price,
               p.description AS description
        LIMIT $limit
        """

        with self.driver.session(database=self.database) as session:
            result = session.run(query, limit=limit)
            products = []
            for record in result:
                products.append({
                    "product_id": record["product_id"],
                    "title": record["title"],
                    "image_url": record["image_url"],
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
        self.model = Sam3Model.from_pretrained("facebook/sam3", device_map="auto")
        self.processor = Sam3Processor.from_pretrained("facebook/sam3")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[SAM3] Model loaded on {self.device}")

    def segment_image(
        self,
        image: Image.Image,
        text_prompts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Segment image with SAM3 and return all outputs

        Args:
            image: PIL Image
            text_prompts: Optional list of text prompts (e.g., ["clothing", "dress", "shirt"])

        Returns:
            Dictionary with masks, scores, embeddings, and other outputs
        """
        if text_prompts is None:
            # Default prompts for fashion products
            text_prompts = ["clothing", "garment", "product"]

        # Prepare inputs
        inputs = self.processor(image, text=text_prompts, return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        # Run inference
        with torch.no_grad():
            outputs = self.model(**inputs)

        # Post-process masks
        masks = self.processor.post_process_masks(
            outputs.pred_masks,
            inputs["original_sizes"],
            inputs["reshaped_input_sizes"]
        )

        # Extract all outputs
        results = {
            "masks": masks[0].cpu().numpy(),  # Segmentation masks
            "iou_scores": outputs.iou_scores[0].cpu().numpy(),  # IoU confidence scores
            "pred_masks": outputs.pred_masks[0].cpu().numpy(),  # Raw predicted masks
            "image_size": image.size,
            "num_masks": len(masks[0]),
            "text_prompts": text_prompts
        }

        # Include embeddings if available
        if hasattr(outputs, 'vision_embeddings') and outputs.vision_embeddings is not None:
            results["vision_embeddings"] = outputs.vision_embeddings[0].cpu().numpy()

        if hasattr(outputs, 'image_embeddings') and outputs.image_embeddings is not None:
            results["image_embeddings"] = outputs.image_embeddings[0].cpu().numpy()

        return results


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
            # Convert boolean mask to image
            mask_img = Image.fromarray((mask * 255).astype(np.uint8))
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
                axes[idx + 1].imshow(image)
                axes[idx + 1].imshow(mask, alpha=0.5, cmap='jet')
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
        output_dir: Path
    ):
        """Save comprehensive metadata as JSON"""
        metadata = {
            "product_info": product_info,
            "segmentation_results": {
                "num_masks": sam3_results["num_masks"],
                "image_size": sam3_results["image_size"],
                "text_prompts": sam3_results["text_prompts"],
                "iou_scores": sam3_results["iou_scores"].tolist(),
                "mask_files": mask_files,
                "overlay_file": overlay_file
            },
            "embeddings": {
                "has_vision_embeddings": "vision_embeddings" in sam3_results,
                "has_image_embeddings": "image_embeddings" in sam3_results,
                "vision_embedding_shape": sam3_results.get("vision_embeddings", np.array([])).shape,
                "image_embedding_shape": sam3_results.get("image_embeddings", np.array([])).shape
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
        """Save embeddings as .npy files for later use"""
        embedding_files = {}

        if "vision_embeddings" in sam3_results:
            emb_file = output_dir / f"{product_id}_vision_embeddings.npy"
            np.save(emb_file, sam3_results["vision_embeddings"])
            embedding_files["vision"] = str(emb_file)

        if "image_embeddings" in sam3_results:
            emb_file = output_dir / f"{product_id}_image_embeddings.npy"
            np.save(emb_file, sam3_results["image_embeddings"])
            embedding_files["image"] = str(emb_file)

        return embedding_files


async def main():
    """Main pipeline execution"""

    # Configuration
    NUM_PRODUCTS = int(os.getenv("NUM_PRODUCTS", "10"))  # Number of products to process

    print(f"\n[CONFIG] Processing {NUM_PRODUCTS} products")

    # Step 1: Connect to Neo4j
    print("\n[1/5] Connecting to Neo4j...")
    neo4j_conn = Neo4jConnection(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE)

    try:
        # Step 2: Query products with images
        print(f"[2/5] Querying {NUM_PRODUCTS} products with images...")
        products = neo4j_conn.query_products_with_images(limit=NUM_PRODUCTS)
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

            # Segment with SAM3
            print("  • Running SAM3 segmentation...")
            sam3_results = sam3_processor.segment_image(
                image,
                text_prompts=["clothing", "product", "garment", "item"]
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

            # Save embeddings
            print("  • Saving embeddings...")
            embedding_files = saver.save_embeddings(
                sam3_results,
                product_id,
                RESULTS_DIR
            )
            if embedding_files:
                print(f"  ✓ Saved {len(embedding_files)} embedding files")

            # Save metadata
            print("  • Saving metadata...")
            metadata_file = saver.save_metadata(
                product,
                sam3_results,
                mask_files,
                overlay_file,
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
