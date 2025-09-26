#!/usr/bin/env python3
"""
TURBO FashionSigLIP Processing - Optimized for Speed
Target: Process 6M products in 2-4 days instead of 12+ days

Optimizations:
- Large batch sizes (2000-4000 products)
- High parallelism (50-100 concurrent downloads)
- Batch model inference
- Skip all validation
- Aggressive caching
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
from concurrent.futures import ThreadPoolExecutor
import aiohttp
import numpy as np

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fashionsig_turbo")

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class TurboFashionSigProcessor:
    def __init__(self):
        self.model = None
        self.processor = None
        self.device = None
        self.torch = None
        self.np = None
        self.qdrant_client = None
        self.collection_name = "fashion_fashionsig_768d"
        self.checkpoint_file = "fashionsig_turbo_checkpoint.json"

        # Aggressive settings for speed
        self.batch_size = int(os.getenv('BATCH_SIZE', '2000'))  # 4x larger batches
        self.max_concurrent = int(os.getenv('MAX_CONCURRENT', '80'))  # 8x more parallel

        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'start_time': None,
            'last_processed_id': None,
            'current_rate': 0
        }

    def load_checkpoint(self):
        """Load processing checkpoint"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    checkpoint = json.load(f)
                self.stats.update(checkpoint)
                logger.info(f"Resumed from checkpoint: {self.stats['total_processed']:,} products processed")
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
        """Load FashionSigLIP model once"""
        if self.model is not None:
            logger.info("Model already loaded")
            return True

        try:
            logger.info("Loading FashionSigLIP model (TURBO mode)...")
            sys.path.append('/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')

            from run_fashionsig_precomputation import setup_fashionsig, setup_qdrant

            # Load model
            self.processor, self.model, self.device, self.torch, self.np = setup_fashionsig()
            if self.model is None:
                return False

            # Setup Qdrant
            self.qdrant_client, VectorParams, Distance = setup_qdrant()
            if self.qdrant_client is None:
                return False

            logger.info(f"TURBO model loaded (batch_size={self.batch_size}, concurrent={self.max_concurrent})")
            return True

        except Exception as e:
            logger.error(f"Model initialization failed: {e}")
            return False

    async def get_products_batch_cursor(self):
        """Get large batch using cursor pagination"""
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
                if self.stats['last_processed_id']:
                    query = f"""
                        MATCH (p:Product)
                        WHERE p.images IS NOT NULL
                          AND p.id > '{self.stats['last_processed_id']}'
                        RETURN p.id, p.title, p.images
                        ORDER BY p.id
                        LIMIT {self.batch_size}
                    """
                else:
                    query = f"""
                        MATCH (p:Product)
                        WHERE p.images IS NOT NULL
                        RETURN p.id, p.title, p.images
                        ORDER BY p.id
                        LIMIT {self.batch_size}
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

                    if images_data:  # Only add products with images
                        products.append({
                            'id': product_id,
                            'title': title,
                            'image_url': images_data[0]  # Take first image
                        })

                if products:
                    self.stats['last_processed_id'] = products[-1]['id']
                    logger.info(f"TURBO batch: {len(products)} products (cursor: {products[0]['id']} -> {products[-1]['id']})")

                return products

        except Exception as e:
            logger.error(f"Product fetching failed: {e}")
            return []

    async def download_images_batch(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Download all images concurrently with high parallelism"""
        logger.info(f"Downloading {len(products)} images with {self.max_concurrent} concurrent connections...")

        downloaded_products = {}
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def download_single(session, product):
            async with semaphore:
                try:
                    async with session.get(product['image_url'], timeout=aiohttp.ClientTimeout(total=15)) as response:
                        if response.status == 200 and 'image' in response.headers.get('content-type', ''):
                            content = await response.read()
                            return product['id'], {
                                'product': product,
                                'image_data': content
                            }
                except:
                    pass
                return product['id'], None

        # Create session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent * 2,  # Connection pool
            limit_per_host=20,
            ttl_dns_cache=300,
            use_dns_cache=True
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [download_single(session, product) for product in products]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, tuple) and result[1] is not None:
                    product_id, data = result
                    downloaded_products[product_id] = data

        success_rate = len(downloaded_products) / len(products) * 100
        logger.info(f"Downloaded {len(downloaded_products)}/{len(products)} images ({success_rate:.1f}% success)")

        return downloaded_products

    async def process_images_batch(self, downloaded_products: Dict[str, Any]) -> int:
        """Process all downloaded images in batches through the model"""
        if not downloaded_products:
            return 0

        logger.info(f"Processing {len(downloaded_products)} images through FashionSigLIP...")

        # Prepare images and texts in batches
        batch_images = []
        batch_texts = []
        product_ids = []

        try:
            from PIL import Image
            from io import BytesIO

            for product_id, data in downloaded_products.items():
                try:
                    # Load image
                    img = Image.open(BytesIO(data['image_data'])).convert('RGB')
                    batch_images.append(img)

                    # Prepare text
                    title = data['product']['title']
                    text_words = title.split()[:40]
                    text = " ".join(text_words)
                    batch_texts.append(text)

                    product_ids.append(product_id)

                except Exception as img_error:
                    logger.debug(f"Warning Image prep failed for {product_id}: {img_error}")
                    continue

            if not batch_images:
                return 0

            # Process entire batch through model at once
            logger.info(f"Running batch inference on {len(batch_images)} images...")

            inputs = self.processor(
                text=batch_texts,
                images=batch_images,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=64
            )

            if 'attention_mask' in inputs:
                del inputs['attention_mask']

            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with self.torch.no_grad():
                outputs = self.model(**inputs)

                if isinstance(outputs, tuple) and len(outputs) == 4:
                    image_embeddings = outputs[2].cpu().numpy()  # Shape: [batch_size, 768]
                    text_embeddings = outputs[3].cpu().numpy()   # Shape: [batch_size, 768]
                else:
                    logger.error("Unexpected model output format")
                    return 0

            # Store all embeddings in Qdrant as batch
            await self.store_embeddings_batch(product_ids, downloaded_products, image_embeddings, text_embeddings)

            return len(product_ids)

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            import traceback
            traceback.print_exc()
            return 0

    async def store_embeddings_batch(self, product_ids: List[str], downloaded_products: Dict[str, Any],
                                   image_embeddings: np.ndarray, text_embeddings: np.ndarray):
        """Store all embeddings in Qdrant as a single batch operation"""
        try:
            import hashlib
            import uuid
            from qdrant_client.models import PointStruct

            points = []

            for i, product_id in enumerate(product_ids):
                try:
                    image_emb = image_embeddings[i].flatten()
                    text_emb = text_embeddings[i].flatten()
                    combined_emb = self.np.concatenate([image_emb, text_emb])

                    # Generate point ID
                    unique_string = f"{product_id}_img_0"
                    hash_object = hashlib.md5(unique_string.encode())
                    point_id = str(uuid.UUID(hash_object.hexdigest()))

                    point = PointStruct(
                        id=point_id,
                        vector={
                            "image": image_emb.tolist(),
                            "text": text_emb.tolist(),
                            "combined": combined_emb.tolist()
                        },
                        payload={
                            "product_id": product_id,
                            "title": downloaded_products[product_id]['product']['title'],
                            "image_url": downloaded_products[product_id]['product']['image_url'],
                            "model_used": "Marqo/marqo-fashionSigLIP",
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    points.append(point)

                except Exception as point_error:
                    logger.debug(f"Point creation failed for {product_id}: {point_error}")
                    continue

            if points:
                # Batch upload to Qdrant
                logger.info(f"Uploading {len(points)} embeddings to Qdrant...")
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                logger.info(f"Batch upload complete: {len(points)} embeddings stored")

        except Exception as e:
            logger.error(f"Batch storage failed: {e}")

    async def run_turbo_processing(self, target_products: int = 6_000_000):
        """Run TURBO processing for 6M products"""
        logger.info(f"TURBO MODE: Processing {target_products:,} products")
        logger.info(f"Batch size: {self.batch_size:,}, Concurrent: {self.max_concurrent}")

        # Load checkpoint
        self.load_checkpoint()

        if not self.stats['start_time']:
            self.stats['start_time'] = datetime.now().isoformat()

        # Initialize model once
        if not await self.initialize_model():
            return False

        batch_count = 0
        start_time = time.time()

        try:
            while self.stats['total_processed'] < target_products:
                batch_count += 1
                batch_start_time = time.time()

                logger.info(f"{'='*80}")
                logger.info(f"TURBO BATCH {batch_count} (processed: {self.stats['total_processed']:,})")
                logger.info(f"{'='*80}")

                # Get large batch
                products = await self.get_products_batch_cursor()
                if not products:
                    logger.info("No more products to process")
                    break

                # Download images with high concurrency
                downloaded_products = await self.download_images_batch(products)

                # Process through model in batch
                successful_count = await self.process_images_batch(downloaded_products)

                # Update stats
                self.stats['total_processed'] += len(products)
                self.stats['successful'] += successful_count
                self.stats['failed'] += len(products) - successful_count

                # Calculate performance metrics
                batch_time = time.time() - batch_start_time
                total_time = time.time() - start_time
                current_rate = len(products) / batch_time * 60  # products/minute
                overall_rate = self.stats['total_processed'] / total_time * 60

                self.stats['current_rate'] = current_rate

                # ETA calculation
                remaining_products = target_products - self.stats['total_processed']
                eta_minutes = remaining_products / overall_rate if overall_rate > 0 else 0
                eta_hours = eta_minutes / 60
                eta_days = eta_hours / 24

                # Progress report
                progress_pct = (self.stats['total_processed'] / target_products) * 100
                success_rate = (self.stats['successful'] / self.stats['total_processed']) * 100

                logger.info(f"TURBO PERFORMANCE:")
                logger.info(f"   Progress: {self.stats['total_processed']:,}/{target_products:,} ({progress_pct:.1f}%)")
                logger.info(f"   Success Rate: {self.stats['successful']:,} ({success_rate:.1f}%)")
                logger.info(f"   Current Rate: {current_rate:.0f} products/minute")
                logger.info(f"   Overall Rate: {overall_rate:.0f} products/minute")
                logger.info(f"   ETA: {eta_days:.1f} days ({eta_hours:.1f} hours)")

                # Save checkpoint every 5 batches (more frequent for large batches)
                if batch_count % 5 == 0:
                    self.save_checkpoint()

                # Small delay
                await asyncio.sleep(0.5)

        except KeyboardInterrupt:
            logger.info("TURBO processing interrupted by user")
        except Exception as e:
            logger.error(f"TURBO processing failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.save_checkpoint()

            # Final summary
            total_time = time.time() - start_time
            overall_rate = self.stats['successful'] / (total_time / 60) if total_time > 0 else 0

            logger.info(f"TURBO FINAL SUMMARY:")
            logger.info(f"   Total processed: {self.stats['total_processed']:,}")
            logger.info(f"   Successful: {self.stats['successful']:,}")
            logger.info(f"   Overall rate: {overall_rate:.0f} products/minute")
            logger.info(f"   Time elapsed: {total_time/3600:.1f} hours")

        return self.stats['successful'] > 0

async def main():
    """Main function"""
    processor = TurboFashionSigProcessor()

    target_products = int(os.getenv('TARGET_PRODUCTS', '6000000'))
    success = await processor.run_turbo_processing(target_products)
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)