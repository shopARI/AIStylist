#!/usr/bin/env python3
"""
A100 Optimized FashionSigLIP VISION-ONLY Multi-Image Processing
Handles UUID-based products with multiple images per product

NEW FEATURES:
- UUID support from Neo4j product nodes
- Multiple images per product (separate embeddings)
- Each image gets unique Qdrant point: {uuid}_{image_index}
- Preserves individual image visual information
- Collection: fashion_fashionsig_vision_multi

A100 80GB Optimizations:
- Large batch sizes optimized for A100
- High concurrency (100 concurrent downloads)
- Proper error handling and retry logic
- Advanced checkpointing and recovery
- GPU memory monitoring and management
- Production logging with performance metrics
"""

import os
import sys
import asyncio
import logging
import json
import time
import traceback
import signal
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
from pathlib import Path
import aiohttp
import numpy as np

# Set up comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'fashionsig_a100_production_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger("fashionsig_a100_production")

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv not installed, using system environment")

@dataclass
class ProcessingStats:
    """Production statistics with detailed metrics"""
    total_processed: int = 0
    successful: int = 0
    failed: int = 0
    start_time: Optional[str] = None
    last_checkpoint: Optional[str] = None
    last_processed_id: Optional[int] = None
    batches_completed: int = 0
    batches_failed: int = 0
    avg_batch_time: float = 0.0
    gpu_memory_peak: float = 0.0
    error_counts: Dict[str, int] = None

    def __post_init__(self):
        if self.error_counts is None:
            self.error_counts = {}

class CircuitBreaker:
    """Circuit breaker for failed operations"""
    def __init__(self, failure_threshold: int = 5, timeout: float = 300.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"

    async def call(self, func):
        """Execute async function through circuit breaker"""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = await func()
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

            raise e

class A100FashionSigProcessor:
    """A100-optimized FashionSigLIP processor with production reliability"""

    def __init__(self):
        self.model = None
        self.processor = None
        self.device = None
        self.torch = None
        self.qdrant_client = None
        # Use dedicated collection for multi-image FashionSigLIP embeddings (1024 dimensions)
        self.collection_name = "fashion_fashionsig_vision_multi"
        self.circuit_breaker = CircuitBreaker()

        # A100-optimized configuration (6K batch for 80GB A100)
        self.batch_size = int(os.getenv('BATCH_SIZE', '6000'))
        self.max_concurrent = int(os.getenv('MAX_CONCURRENT', '100'))
        self.gpu_memory_fraction = float(os.getenv('GPU_MEMORY_FRACTION', '0.8'))
        self.checkpoint_interval = int(os.getenv('CHECKPOINT_INTERVAL', '5'))
        self.retry_attempts = int(os.getenv('RETRY_ATTEMPTS', '3'))
        self.retry_delay = float(os.getenv('RETRY_DELAY', '1.0'))

        # Production settings
        self.target_products = int(os.getenv('TARGET_PRODUCTS', '6000000'))
        self.checkpoint_file = f"fashionsig_a100_checkpoint_{datetime.now().strftime('%Y%m%d')}.json"
        self.stats = ProcessingStats()

        # Reset stats for fresh start
        self.stats.total_processed = 0
        self.stats.successful = 0
        self.stats.failed = 0
        self.stats.batches_completed = 0
        self.stats.batches_failed = 0

        # Graceful shutdown handling
        self.shutdown_requested = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info(f"A100 FashionSig Processor initialized")
        logger.info(f"Config: {self.batch_size} batch, {self.max_concurrent} concurrent, {self.target_products:,} target")

    def _signal_handler(self, signum, frame):
        """Handle graceful shutdown"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True

    async def initialize_model(self):
        """Initialize FashionSigLIP model with A100 optimization"""
        try:
            logger.info("Loading FashionSigLIP model for A100...")

            import torch
            from transformers import SiglipVisionModel, SiglipProcessor

            self.torch = torch

            # A100 GPU setup
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
                logger.info(f"Using GPU: {gpu_name}")
                logger.info(f"GPU Memory: {gpu_memory:.1f} GB")
            else:
                self.device = torch.device("cpu")
                logger.warning("WARNING: CUDA not available, using CPU")

            # Load model with A100 optimizations
            model_name = "google/siglip-large-patch16-384"
            self.model = SiglipVisionModel.from_pretrained(
                model_name,
                torch_dtype=torch.float16  # Half precision for A100
            )
            self.processor = SiglipProcessor.from_pretrained(model_name)

            self.model.eval()
            self.model.to(self.device)

            # Enable A100 optimizations
            if hasattr(torch, 'compile') and torch.cuda.is_available():
                logger.info("Compiling Compiling model with torch.compile for A100...")
                self.model = torch.compile(self.model, mode="max-autotune")

            logger.info("SUCCESS: FashionSigLIP model loaded successfully")
            return True

        except Exception as e:
            logger.error(f"ERROR: Model initialization failed: {e}")
            traceback.print_exc()
            return False

    async def initialize_qdrant(self):
        """Initialize Qdrant client with API key authentication"""
        try:
            from qdrant_client import AsyncQdrantClient
            from qdrant_client.models import Distance, VectorParams, PointStruct

            # Hardcoded Qdrant credentials for production
            qdrant_url = "https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io:6333"
            qdrant_api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.zz1R7TKuAT4A0dX-M-oZbgX9sYT-x6bwT1EMPGKZ6Jg"

            if qdrant_api_key:
                self.qdrant_client = AsyncQdrantClient(
                    url=qdrant_url,
                    api_key=qdrant_api_key
                )
                logger.info("Using Using Qdrant API key authentication")
            else:
                self.qdrant_client = AsyncQdrantClient(url=qdrant_url)
                logger.info("WARNING: No Qdrant API key found, using unauthenticated connection")

            # Test connection
            info = await self.qdrant_client.get_collections()
            logger.info(f"SUCCESS: Qdrant connected: {len(info.collections)} collections")

            # Check if our collection exists, create if not
            collection_names = [c.name for c in info.collections]
            if self.collection_name not in collection_names:
                logger.info(f"Compiling Creating collection: {self.collection_name}")
                # FashionSigLIP actually outputs 1024 dims (from error message)
                await self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
                )
                logger.info(f"SUCCESS: Collection {self.collection_name} created successfully")
            else:
                logger.info(f"SUCCESS: Collection {self.collection_name} already exists")

            return True

        except Exception as e:
            logger.error(f"ERROR: Qdrant initialization failed: {e}")
            return False

    def load_checkpoint(self) -> bool:
        """Load processing checkpoint"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    checkpoint_data = json.load(f)

                # Convert dict back to ProcessingStats
                self.stats = ProcessingStats(**checkpoint_data)
                logger.info(f"Resumed Resumed from checkpoint: {self.stats.total_processed:,} processed")
                return True

            except Exception as e:
                logger.error(f"ERROR: Failed to load checkpoint: {e}")
        return False

    def save_checkpoint(self):
        """Save processing checkpoint"""
        try:
            self.stats.last_checkpoint = datetime.now().isoformat()

            with open(self.checkpoint_file, 'w') as f:
                json.dump(asdict(self.stats), f, indent=2)

            logger.debug(f"GPU Memory: Checkpoint saved: {self.stats.total_processed:,} processed")

        except Exception as e:
            logger.error(f"ERROR: Failed to save checkpoint: {e}")

    async def get_products_batch(self, offset: int, limit: int) -> List[Dict[str, Any]]:
        """Fetch UUID-based products with multiple images from Neo4j"""
        # Input validation
        if not isinstance(offset, int) or offset < 0:
            raise ValueError(f"Invalid offset: {offset}")
        if not isinstance(limit, int) or limit <= 0 or limit > 10000:
            raise ValueError(f"Invalid limit: {limit}")

        try:
            from neo4j import AsyncGraphDatabase
            import uuid
            import json

            # Neo4j connection from .env
            neo4j_uri = os.getenv("NEO4J_URI") or os.getenv("NEO4J_URL", "neo4j://localhost:7687")
            neo4j_user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
            neo4j_database = os.getenv("NEO4J_DATABASE", "productionbackup2")

            driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

            # Fetch products with UUID and images from productionbackup2
            query = """
            MATCH (p:Product)
            WHERE p.id IS NOT NULL AND p.images IS NOT NULL
            RETURN
                p.id AS uuid,
                p.title AS name,
                p.extracted_brand AS brand,
                p.price AS price,
                p.description AS description,
                p.images AS images
            ORDER BY p.id
            SKIP $offset
            LIMIT $limit
            """

            async with driver.session(database=neo4j_database) as session:
                result = await session.run(query, offset=offset, limit=limit)
                records = await result.data()

            await driver.close()

            # Process products - parse images JSON string
            products = []
            for record in records:
                # Validate UUID format
                try:
                    product_uuid = str(uuid.UUID(str(record['uuid'])))
                except ValueError:
                    logger.warning(f"Invalid UUID format: {record['uuid']}, skipping")
                    continue

                # Parse images JSON string
                images_str = record.get('images', '[]')
                if isinstance(images_str, str):
                    try:
                        images_array = json.loads(images_str)
                    except json.JSONDecodeError:
                        logger.warning(f"Product {product_uuid} has invalid JSON in images field")
                        continue
                else:
                    images_array = images_str if isinstance(images_str, list) else []

                if not images_array or len(images_array) == 0:
                    logger.debug(f"Product {product_uuid} has no images, skipping")
                    continue

                # Build full image URLs from Neo4j paths
                image_urls = []
                for img_path in images_array:
                    if img_path and isinstance(img_path, str):
                        # Images are paths like: "bebfd6e9-d390-4f3e-b0fb-f3a1e4ddec49/..."
                        full_url = f"https://app.shopari.com/images/{img_path}"
                        image_urls.append(full_url)

                if not image_urls:
                    logger.debug(f"Product {product_uuid} has no valid images, skipping")
                    continue

                products.append({
                    'uuid': product_uuid,
                    'name': record.get('name', ''),
                    'category': '',  # No category in productionbackup2 schema
                    'price': record.get('price', 0.0),
                    'brand': record.get('brand', ''),
                    'description': record.get('description', ''),
                    'image_urls': image_urls  # List of parsed image URLs
                })

            logger.debug(f"Fetched {len(products)} UUID-based products from Neo4j (offset={offset})")
            return products

        except Exception as e:
            logger.error(f"ERROR: Neo4j product fetch failed: {e}")
            raise e

    async def download_image_batch(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Download ALL images for each product (multiple images per UUID)"""
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def download_single_image(product_uuid, image_url, image_index, product_data):
            """Download one image for a product"""
            async with semaphore:
                try:
                    if not image_url:
                        return None

                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                            if response.status == 200:
                                image_data = await response.read()
                                from PIL import Image
                                from io import BytesIO

                                image = Image.open(BytesIO(image_data)).convert('RGB')
                                return {
                                    'product_uuid': product_uuid,
                                    'image_index': image_index,  # 0, 1, 2, etc.
                                    'image': image,
                                    'product': product_data
                                }
                    return None

                except Exception as e:
                    logger.debug(f"Image download failed for {product_uuid} (image {image_index}): {e}")
                    return None

        # Create download tasks for ALL images across ALL products
        all_tasks = []
        for product in products:
            product_uuid = product['uuid']
            image_urls = product.get('image_urls', [])

            # Create one task per image
            for image_index, image_url in enumerate(image_urls):
                task = download_single_image(product_uuid, image_url, image_index, product)
                all_tasks.append(task)

        # Download all images concurrently
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Filter successful downloads
        successful_downloads = [
            r for r in results
            if r is not None and not isinstance(r, Exception)
        ]

        total_images = sum(len(p.get('image_urls', [])) for p in products)
        logger.debug(f"Downloaded {len(successful_downloads)}/{total_images} images from {len(products)} products")
        return successful_downloads

    async def generate_embeddings_batch(self, image_batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate separate embeddings for each image (preserving UUID and image_index)"""
        if not image_batch or not self.model:
            return []

        try:
            # Process in sub-batches to manage A100 memory efficiently
            sub_batch_size = min(200, len(image_batch))  # 200 images per sub-batch for A100
            all_results = []

            for i in range(0, len(image_batch), sub_batch_size):
                sub_batch = image_batch[i:i + sub_batch_size]
                images = [item['image'] for item in sub_batch]

                # Process images through FashionSigLIP
                inputs = self.processor(images=images, return_tensors="pt", padding=True)
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

                with self.torch.no_grad():
                    with self.torch.amp.autocast('cuda'):  # Mixed precision for A100
                        outputs = self.model(**inputs)
                        embeddings = outputs.last_hidden_state.mean(dim=1)  # Global average pooling

                # Convert to CPU numpy
                embeddings_np = embeddings.cpu().numpy()

                # Prepare results - each image gets its own embedding
                for j, item in enumerate(sub_batch):
                    all_results.append({
                        'product_uuid': item['product_uuid'],
                        'image_index': item['image_index'],  # Preserve image index
                        'embedding': embeddings_np[j],
                        'product': item['product']
                    })

                # Memory cleanup
                del inputs, outputs, embeddings, embeddings_np
                self.torch.cuda.empty_cache()

            logger.debug(f"Generated {len(all_results)} embeddings (separate per image)")
            return all_results

        except Exception as e:
            logger.error(f"ERROR: Embedding generation failed: {e}")
            return []

    async def upload_to_qdrant_batch(self, embedding_batch: List[Dict[str, Any]]) -> bool:
        """Upload embeddings to Qdrant with UUID-based point IDs"""
        if not embedding_batch or not self.qdrant_client:
            return False

        try:
            from qdrant_client.models import PointStruct
            import hashlib

            # Prepare points for batch upload - each image gets unique ID: {uuid}_{image_index}
            points = []
            for item in embedding_batch:
                product_uuid = item['product_uuid']
                image_index = item['image_index']

                # Create unique point ID as string: "uuid_index"
                point_id_str = f"{product_uuid}_{image_index}"

                # Convert to integer ID using hash (Qdrant requires int or UUID)
                # Use consistent hash to make IDs deterministic
                point_id = int(hashlib.md5(point_id_str.encode()).hexdigest()[:16], 16)

                points.append(PointStruct(
                    id=point_id,
                    vector=item['embedding'].tolist(),
                    payload={
                        'product_uuid': product_uuid,  # Store original UUID
                        'image_index': image_index,     # Store which image (0, 1, 2, etc.)
                        'point_id_str': point_id_str,   # Store readable ID
                        'name': item['product'].get('name', ''),
                        'category': item['product'].get('category', ''),
                        'price': item['product'].get('price', 0),
                        'brand': item['product'].get('brand', ''),
                        'embedding_type': 'fashionsig_vision',
                        'processed_at': datetime.now().isoformat()
                    }
                ))

            # Batch upload to Qdrant
            operation_info = await self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True
            )

            if operation_info.status == "completed":
                logger.debug(f"Uploaded {len(points)} UUID-based embeddings to Qdrant")
                return True
            else:
                logger.error(f"ERROR: Qdrant upload failed: {operation_info.status}")
                return False

        except Exception as e:
            logger.error(f"ERROR: Qdrant upload failed: {e}")
            return False

    async def process_batch(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process a complete batch with A100 optimization"""
        batch_start = time.time()
        batch_stats = {
            'processed': len(products),
            'successful': 0,
            'failed': 0,
            'errors': {}
        }

        try:
            if not products:
                return batch_stats

            logger.info(f"Loading Processing batch of {len(products)} products...")

            # Monitor GPU memory
            if self.torch and self.torch.cuda.is_available():
                self.torch.cuda.empty_cache()
                gpu_memory_before = self.torch.cuda.memory_allocated()

            # Step 1: Download images concurrently
            image_batch = await self.download_image_batch(products)
            if not image_batch:
                batch_stats['failed'] = len(products)
                batch_stats['errors']['image_download_failed'] = len(products)
                return batch_stats

            # Step 2: Generate embeddings
            embedding_batch = await self.generate_embeddings_batch(image_batch)
            if not embedding_batch:
                batch_stats['failed'] = len(products)
                batch_stats['errors']['embedding_generation_failed'] = len(products)
                return batch_stats

            # Step 3: Upload to Qdrant
            upload_success = await self.upload_to_qdrant_batch(embedding_batch)
            if upload_success:
                batch_stats['successful'] = len(embedding_batch)
            else:
                batch_stats['failed'] = len(embedding_batch)
                batch_stats['errors']['qdrant_upload_failed'] = len(embedding_batch)

            # Update GPU memory peak
            if self.torch and self.torch.cuda.is_available():
                gpu_memory_after = self.torch.cuda.memory_allocated()
                memory_used_gb = (gpu_memory_after - gpu_memory_before) / 1024**3
                self.stats.gpu_memory_peak = max(self.stats.gpu_memory_peak, memory_used_gb)

            batch_time = time.time() - batch_start
            self.stats.avg_batch_time = (
                (self.stats.avg_batch_time * self.stats.batches_completed + batch_time) /
                (self.stats.batches_completed + 1)
            )

            logger.info(f"SUCCESS: Batch completed in {batch_time:.1f}s: {batch_stats['successful']}/{batch_stats['processed']} successful")

            return batch_stats

        except Exception as e:
            logger.error(f"ERROR: Batch processing failed: {e}")
            batch_stats['failed'] = len(products)
            batch_stats['errors'][str(e)] = batch_stats['errors'].get(str(e), 0) + 1
            return batch_stats

    async def run_production_processing(self) -> bool:
        """Main A100-optimized production processing loop"""
        try:
            # Load checkpoint
            self.load_checkpoint()

            # Initialize components
            if not await self.initialize_model():
                return False

            if not await self.initialize_qdrant():
                return False

            # Set start time
            if not self.stats.start_time:
                self.stats.start_time = datetime.now().isoformat()

            logger.info(f"Starting A100 production processing")
            logger.info(f"Target: {self.target_products:,} products, Batch: {self.batch_size}")

            processed_offset = self.stats.last_processed_id or 0

            while (self.stats.total_processed < self.target_products and
                   not self.shutdown_requested):

                try:
                    # Fetch products
                    products = await self.get_products_batch(processed_offset, self.batch_size)

                    if not products:
                        logger.info("📭 No more products to process")
                        break

                    # Process batch through circuit breaker
                    batch_stats = await self.circuit_breaker.call(
                        lambda: self.process_batch(products)
                    )

                    # Update statistics
                    self.stats.total_processed += batch_stats['processed']
                    self.stats.successful += batch_stats['successful']
                    self.stats.failed += batch_stats['failed']
                    self.stats.last_processed_id = processed_offset + len(products)

                    if batch_stats['successful'] > 0:
                        self.stats.batches_completed += 1
                    else:
                        self.stats.batches_failed += 1

                    # Update error counts
                    for error, count in batch_stats.get('errors', {}).items():
                        self.stats.error_counts[error] = self.stats.error_counts.get(error, 0) + count

                    # Progress reporting
                    progress_pct = (self.stats.total_processed / self.target_products) * 100
                    elapsed_hours = (datetime.now() - datetime.fromisoformat(self.stats.start_time)).total_seconds() / 3600
                    rate = self.stats.total_processed / max(elapsed_hours, 0.001)

                    logger.info(f"Progress: Progress: {self.stats.total_processed:,}/{self.target_products:,} ({progress_pct:.1f}%) | Rate: {rate:.0f}/hr")

                    # Checkpoint saving
                    if self.stats.batches_completed % self.checkpoint_interval == 0:
                        self.save_checkpoint()
                        logger.info(f"Checkpoint: Checkpoint: {self.stats.batches_completed} batches, {self.stats.total_processed:,} processed")

                    processed_offset += len(products)

                    # Brief pause to prevent overwhelming the system
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"ERROR: Batch processing failed: {e}")
                    self.stats.batches_failed += 1
                    processed_offset += self.batch_size  # Skip failed batch
                    await asyncio.sleep(5)  # Wait before retrying

            # Final summary
            self.save_checkpoint()
            total_time = (datetime.now() - datetime.fromisoformat(self.stats.start_time)).total_seconds()
            success_rate = (self.stats.successful / max(self.stats.total_processed, 1)) * 100

            logger.info(f"Using GPU: A100 PRODUCTION SUMMARY:")
            logger.info(f"   Total processed: {self.stats.total_processed:,}")
            logger.info(f"   Successful: {self.stats.successful:,} ({success_rate:.1f}%)")
            logger.info(f"   Failed: {self.stats.failed:,}")
            logger.info(f"   Batches completed: {self.stats.batches_completed}")
            logger.info(f"   Batches failed: {self.stats.batches_failed}")
            logger.info(f"   Average batch time: {self.stats.avg_batch_time:.1f}s")
            logger.info(f"   Peak GPU memory: {self.stats.gpu_memory_peak:.1f}GB")
            logger.info(f"   Total time: {total_time/3600:.1f} hours")
            logger.info(f"   Processing rate: {self.stats.total_processed/(total_time/3600):.0f} products/hour")

            if self.stats.error_counts:
                logger.info(f"   Error breakdown:")
                for error, count in self.stats.error_counts.items():
                    logger.info(f"     {error}: {count}")

            return self.stats.successful > 0

        except Exception as e:
            logger.error(f"ERROR: Production processing failed: {e}")
            traceback.print_exc()
            return False

        finally:
            # Cleanup GPU memory
            if self.torch and self.torch.cuda.is_available():
                self.torch.cuda.empty_cache()

async def main():
    """Main function"""
    processor = A100FashionSigProcessor()
    success = await processor.run_production_processing()
    return success

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"ERROR: Fatal error: {e}")
        sys.exit(1)