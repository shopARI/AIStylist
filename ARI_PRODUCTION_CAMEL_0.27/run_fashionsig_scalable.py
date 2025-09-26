#!/usr/bin/env python3
"""
Scalable FashionSigLIP Processing for 6M Products
Optimized for production scale with:
- Cursor-based pagination (no SKIP overhead)
- No URL pre-validation (handle failures during processing)
- Persistent model loading across batches
- Parallel processing within batches
- Checkpoint saving/resuming
"""

import os
import sys
import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import pickle
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fashionsig_scalable")

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class ScalableFashionSigProcessor:
    def __init__(self):
        self.model = None
        self.processor = None
        self.device = None
        self.torch = None
        self.np = None
        self.qdrant_client = None
        self.collection_name = "fashion_fashionsig_768d"
        self.checkpoint_file = "fashionsig_checkpoint.json"
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'start_time': None,
            'last_processed_id': None
        }

    def load_checkpoint(self):
        """Load processing checkpoint to resume from where we left off"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    checkpoint = json.load(f)
                self.stats.update(checkpoint)
                logger.info(f"Resumed from checkpoint: {self.stats['total_processed']:,} products processed")
                logger.info(f"   Last processed ID: {self.stats['last_processed_id']}")
                return True
            except Exception as e:
                logger.warning(f"Could not load checkpoint: {e}")
        return False

    def save_checkpoint(self):
        """Save current progress checkpoint"""
        try:
            checkpoint_data = self.stats.copy()
            checkpoint_data['timestamp'] = datetime.now().isoformat()

            with open(self.checkpoint_file, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)

            logger.info(f"Checkpoint saved: {self.stats['total_processed']:,} products processed")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    async def initialize_model(self):
        """Load FashionSigLIP model once and keep in memory"""
        if self.model is not None:
            logger.info("Model already loaded")
            return True

        try:
            logger.info("Loading FashionSigLIP model (one-time setup)...")
            sys.path.append('/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')

            from run_fashionsig_precomputation import setup_fashionsig, setup_qdrant

            # Load model
            self.processor, self.model, self.device, self.torch, self.np = setup_fashionsig()
            if self.model is None:
                logger.error("Failed to load FashionSigLIP model")
                return False

            # Setup Qdrant
            self.qdrant_client, VectorParams, Distance = setup_qdrant()
            if self.qdrant_client is None:
                logger.error("Failed to setup Qdrant client")
                return False

            logger.info("Model and Qdrant loaded successfully (persistent)")
            return True

        except Exception as e:
            logger.error(f"Model initialization failed: {e}")
            return False

    async def get_products_batch_cursor(self, batch_size: int = 512):
        """Get products using cursor-based pagination (faster than SKIP)"""
        try:
            from neo4j import GraphDatabase

            driver = GraphDatabase.driver(
                os.getenv("NEO4J_URL", "bolt://localhost:7687"),
                auth=(
                    os.getenv("NEO4J_USERNAME", "neo4j"),
                    os.getenv("NEO4J_PASSWORD", "")
                )
            )

            with driver.session() as session:
                # Cursor-based query (much faster than SKIP for large datasets)
                if self.stats['last_processed_id']:
                    query = f"""
                        MATCH (p:Product)
                        WHERE p.images IS NOT NULL
                          AND p.id > '{self.stats['last_processed_id']}'
                        RETURN p.id, p.title, p.images
                        ORDER BY p.id
                        LIMIT {batch_size}
                    """
                else:
                    query = f"""
                        MATCH (p:Product)
                        WHERE p.images IS NOT NULL
                        RETURN p.id, p.title, p.images
                        ORDER BY p.id
                        LIMIT {batch_size}
                    """

                result = session.run(query)

                products = []
                for record in result:
                    product_id = record[0]
                    title = record[1]
                    images_data = record[2]

                    if isinstance(images_data, str):
                        try:
                            images_data = json.loads(images_data)
                        except:
                            images_data = [images_data]

                    products.append({
                        'id': product_id,
                        'title': title,
                        'images': images_data
                    })

                if products:
                    self.stats['last_processed_id'] = products[-1]['id']
                    logger.info(f"Fetched {len(products)} products (cursor: {products[0]['id']} -> {products[-1]['id']})")

                return products

        except Exception as e:
            logger.error(f"Product fetching failed: {e}")
            return []

    async def process_single_product(self, product: Dict[str, Any]) -> bool:
        """Process a single product (called in parallel)"""
        try:
            from io import BytesIO
            from PIL import Image
            import requests
            import hashlib
            import uuid
            from qdrant_client.models import PointStruct

            # Prepare text
            title = product.get('title', '')
            text_words = title.split()[:40]  # Truncate for token limits
            text = " ".join(text_words)

            # Process first image
            img_url = product['images'][0] if product['images'] else None
            if not img_url:
                return False

            # Download image (no pre-validation, just try)
            try:
                response = requests.get(img_url, timeout=10)
                if response.status_code != 200:
                    return False

                img = Image.open(BytesIO(response.content)).convert('RGB')

            except Exception as download_error:
                logger.debug(f"Download failed for {product['id']}: {download_error}")
                return False

            # Generate embeddings
            try:
                inputs = self.processor(
                    text=[text],
                    images=[img],
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=64
                )

                # Remove attention_mask for compatibility
                if 'attention_mask' in inputs:
                    del inputs['attention_mask']

                inputs = {k: v.to(self.device) for k, v in inputs.items()}

                with self.torch.no_grad():
                    outputs = self.model(**inputs)

                    if isinstance(outputs, tuple) and len(outputs) == 4:
                        image_embedding = outputs[2].cpu().numpy().flatten()
                        text_embedding = outputs[3].cpu().numpy().flatten()
                    else:
                        logger.debug(f"Unexpected output format for {product['id']}")
                        return False

            except Exception as model_error:
                logger.debug(f"Model processing failed for {product['id']}: {model_error}")
                return False

            # Store in Qdrant
            try:
                combined_embedding = self.np.concatenate([
                    image_embedding.flatten(),
                    text_embedding.flatten()
                ])

                # Generate unique point ID
                unique_string = f"{product['id']}_img_0"
                hash_object = hashlib.md5(unique_string.encode())
                point_id = str(uuid.UUID(hash_object.hexdigest()))

                point = PointStruct(
                    id=point_id,
                    vector={
                        "image": image_embedding.tolist(),
                        "text": text_embedding.tolist(),
                        "combined": combined_embedding.tolist()
                    },
                    payload={
                        "product_id": product['id'],
                        "title": title,
                        "image_url": img_url,
                        "model_used": "Marqo/marqo-fashionSigLIP",
                        "embedding_dims": len(image_embedding),
                        "timestamp": datetime.now().isoformat()
                    }
                )

                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=[point]
                )

                return True

            except Exception as storage_error:
                logger.debug(f"Storage failed for {product['id']}: {storage_error}")
                return False

        except Exception as e:
            logger.debug(f"Processing failed for {product['id']}: {e}")
            return False

    async def process_batch_parallel(self, products: List[Dict[str, Any]]) -> int:
        """Process a batch of products in parallel"""
        logger.info(f"Processing {len(products)} products in parallel...")

        # Process products concurrently (but limit concurrency to avoid overwhelming servers)
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent downloads

        async def process_with_semaphore(product):
            async with semaphore:
                return await self.process_single_product(product)

        tasks = [process_with_semaphore(product) for product in products]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes
        successful = sum(1 for r in results if r is True)
        failed = len(products) - successful

        self.stats['total_processed'] += len(products)
        self.stats['successful'] += successful
        self.stats['failed'] += failed

        logger.info(f"Batch completed: {successful}/{len(products)} successful ({successful/len(products)*100:.1f}%)")

        return successful

    async def run_production_scale(self, target_products: int = 6_000_000, batch_size: int = 512):
        """Run production-scale processing for millions of products"""
        logger.info(f"Starting PRODUCTION SCALE FashionSigLIP processing")
        logger.info(f"Target: {target_products:,} products in batches of {batch_size}")

        # Load checkpoint if exists
        self.load_checkpoint()

        if not self.stats['start_time']:
            self.stats['start_time'] = datetime.now().isoformat()

        # Initialize model once
        if not await self.initialize_model():
            return False

        batch_count = 0

        try:
            while self.stats['total_processed'] < target_products:
                batch_count += 1

                # Get next batch using cursor-based pagination
                products = await self.get_products_batch_cursor(batch_size)

                if not products:
                    logger.info("No more products to process")
                    break

                logger.info(f"{'='*80}")
                logger.info(f"BATCH {batch_count} (total processed so far: {self.stats['total_processed']:,})")
                logger.info(f"{'='*80}")

                # Process batch in parallel
                successful_count = await self.process_batch_parallel(products)

                # Progress update
                progress_pct = (self.stats['total_processed'] / target_products) * 100
                success_rate = (self.stats['successful'] / self.stats['total_processed']) * 100 if self.stats['total_processed'] > 0 else 0

                logger.info(f"Overall Progress: {self.stats['total_processed']:,}/{target_products:,} ({progress_pct:.1f}%)")
                logger.info(f"Success Rate: {self.stats['successful']:,} successful ({success_rate:.1f}%)")

                # Save checkpoint every 10 batches
                if batch_count % 10 == 0:
                    self.save_checkpoint()

                # Small delay between batches
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Processing interrupted by user")
        except Exception as e:
            logger.error(f"Production processing failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Always save final checkpoint
            self.save_checkpoint()

            # Final summary
            elapsed = time.time() - time.mktime(datetime.fromisoformat(self.stats['start_time']).timetuple()) if self.stats['start_time'] else 0
            logger.info(f"FINAL SUMMARY:")
            logger.info(f"   Total processed: {self.stats['total_processed']:,}")
            logger.info(f"   Successful: {self.stats['successful']:,}")
            logger.info(f"   Failed: {self.stats['failed']:,}")
            logger.info(f"   Success rate: {self.stats['successful']/self.stats['total_processed']*100:.1f}%")
            logger.info(f"   Elapsed time: {elapsed/3600:.1f} hours")
            if self.stats['successful'] > 0:
                logger.info(f"   Rate: {self.stats['successful']/(elapsed/3600):.0f} products/hour")

        return self.stats['successful'] > 0

async def main():
    """Main function"""
    processor = ScalableFashionSigProcessor()

    # Configuration from environment
    target_products = int(os.getenv('TARGET_PRODUCTS', '6000000'))  # 6M default
    batch_size = int(os.getenv('BATCH_SIZE', '512'))

    success = await processor.run_production_scale(target_products, batch_size)
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)