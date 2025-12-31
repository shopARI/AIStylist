#!/usr/bin/env python3
"""
EXTREME FashionSigLIP Processing - 2 DAY TARGET
Process 6M products in 48 hours = 2083 products/minute required

EXTREME Optimizations:
- Massive batches (8000 products)
- Maximum parallelism (200 concurrent)
- Multiple worker processes
- Skip ALL validation/error handling
- Direct Qdrant batch uploads
- Minimal logging
- Memory aggressive caching
"""

import os
import sys
import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, List, Any
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
import aiohttp
import numpy as np

# Minimal logging for speed
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fashionsig_extreme")

class ExtremeFashionSigProcessor:
    def __init__(self):
        self.model = None
        self.processor = None
        self.device = None
        self.torch = None
        self.np = None
        self.qdrant_client = None
        self.collection_name = "fashion_fashionsig_768d"

        # EXTREME settings
        self.batch_size = int(os.getenv('BATCH_SIZE', '8000'))  # 8K per batch
        self.max_concurrent = int(os.getenv('MAX_CONCURRENT', '200'))  # 200 concurrent
        self.num_workers = int(os.getenv('NUM_WORKERS', str(mp.cpu_count())))  # All CPU cores

        self.checkpoint_file = "fashionsig_extreme_checkpoint.json"

        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'start_time': None,
            'last_processed_id': None,
        }

    def load_checkpoint(self):
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    self.stats.update(json.load(f))
                logger.info(f"Resumed: {self.stats['total_processed']:,} processed")
                return True
            except:
                pass
        return False

    def save_checkpoint(self):
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump({**self.stats, 'timestamp': datetime.now().isoformat()}, f)
        except:
            pass

    async def initialize_model(self):
        if self.model is not None:
            return True

        try:
            logger.info("Loading model (EXTREME mode)...")
            sys.path.append('/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')
            from run_fashionsig_precomputation import setup_fashionsig, setup_qdrant

            self.processor, self.model, self.device, self.torch, self.np = setup_fashionsig()
            self.qdrant_client, _, _ = setup_qdrant()

            if self.model is None:
                logger.error("CRITICAL: Model loading failed")
                return False

            if self.qdrant_client is None:
                logger.error("CRITICAL: Qdrant client setup failed")
                return False

            # Test Qdrant connection immediately
            try:
                collections = self.qdrant_client.get_collections()
                collection_names = [c.name for c in collections.collections]
                if self.collection_name not in collection_names:
                    logger.error(f"CRITICAL: Collection '{self.collection_name}' not found in Qdrant")
                    return False
                logger.info(f"Qdrant connection verified - collection '{self.collection_name}' found")
            except Exception as qe:
                logger.error(f"CRITICAL: Qdrant connection test failed: {qe}")
                return False

            logger.info(f"EXTREME loaded: {self.batch_size:,}/batch, {self.max_concurrent} concurrent, {self.num_workers} workers")
            return True
        except Exception as e:
            logger.error(f"CRITICAL Init failed: {e}")
            return False

    async def get_massive_batch(self):
        """Get massive batch with cursor pagination"""
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(
                os.getenv("NEO4J_URL", "bolt://localhost:7687"),
                auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", ""))
            )

            with driver.session() as session:
                if self.stats['last_processed_id']:
                    query = f"""
                        MATCH (p:Product)
                        WHERE p.images IS NOT NULL AND p.id > '{self.stats['last_processed_id']}'
                        RETURN p.id, p.title, p.images
                        ORDER BY p.id LIMIT {self.batch_size}
                    """
                else:
                    query = f"""
                        MATCH (p:Product)
                        WHERE p.images IS NOT NULL
                        RETURN p.id, p.title, p.images
                        ORDER BY p.id LIMIT {self.batch_size}
                    """

                result = session.run(query)
                products = []

                for record in result:
                    images_data = record[2]
                    if isinstance(images_data, str):
                        try:
                            images_data = json.loads(images_data)
                        except:
                            images_data = [images_data]

                    if images_data:
                        products.append({
                            'id': record[0],
                            'title': record[1][:100],  # Truncate early
                            'image_url': images_data[0]
                        })

                if products:
                    self.stats['last_processed_id'] = products[-1]['id']

                return products
        except Exception as e:
            logger.error(f"Batch fetch failed: {e}")
            return []

    async def download_massive_batch(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Download with maximum aggression - 200 concurrent connections"""
        successful_products = []

        # Connection limits pushed to maximum
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent * 3,
            limit_per_host=50,
            ttl_dns_cache=600,
            use_dns_cache=True,
            enable_cleanup_closed=False  # Speed over cleanup
        )

        timeout = aiohttp.ClientTimeout(total=10)  # Short timeout

        async def download_one(session, product):
            try:
                async with session.get(product['image_url'], timeout=timeout) as response:
                    if response.status == 200:
                        content = await response.read()
                        return {**product, 'image_data': content}
            except:
                pass
            return None

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def download_with_semaphore(session, product):
            async with semaphore:
                return await download_one(session, product)

        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [download_with_semaphore(session, p) for p in products]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            successful_products = [r for r in results if r is not None and not isinstance(r, Exception)]

        logger.info(f"Downloaded {len(successful_products)}/{len(products)} ({len(successful_products)/len(products)*100:.0f}%)")
        return successful_products

    def process_model_batch_sync(self, products_data):
        """Synchronous model processing - called by worker processes"""
        try:
            from PIL import Image
            from io import BytesIO

            images = []
            texts = []
            valid_products = []

            # Prepare batch data
            for product in products_data:
                try:
                    img = Image.open(BytesIO(product['image_data'])).convert('RGB')
                    text = " ".join(product['title'].split()[:40])  # Same as other modes

                    images.append(img)
                    texts.append(text)
                    valid_products.append(product)
                except:
                    continue

            if not images:
                return []

            # Model inference
            inputs = self.processor(
                text=texts,
                images=images,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=64  # Same as other modes for identical quality
            )

            if 'attention_mask' in inputs:
                del inputs['attention_mask']

            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with self.torch.no_grad():
                outputs = self.model(**inputs)

            if isinstance(outputs, tuple) and len(outputs) == 4:
                image_embeddings = outputs[2].cpu().numpy()
                text_embeddings = outputs[3].cpu().numpy()

                results = []
                for i, product in enumerate(valid_products):
                    results.append({
                        'product': product,
                        'image_emb': image_embeddings[i],
                        'text_emb': text_embeddings[i]
                    })
                return results

        except Exception as e:
            logger.error(f"Model batch failed: {e}")
            return []

    async def process_with_workers(self, downloaded_products: List[Dict[str, Any]]) -> int:
        """Process using multiple worker processes"""
        if not downloaded_products:
            return 0

        # Split into chunks for workers
        chunk_size = len(downloaded_products) // self.num_workers + 1
        chunks = [downloaded_products[i:i+chunk_size] for i in range(0, len(downloaded_products), chunk_size)]

        logger.info(f"Processing {len(downloaded_products)} products with {len(chunks)} workers...")

        # Process chunks in parallel using processes
        loop = asyncio.get_event_loop()
        with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
            futures = [loop.run_in_executor(executor, self.process_model_batch_sync, chunk) for chunk in chunks]
            results = await asyncio.gather(*futures, return_exceptions=True)

        # Collect all results
        all_embeddings = []
        for result in results:
            if isinstance(result, list):
                all_embeddings.extend(result)

        # Batch upload to Qdrant - CRITICAL FAILURE POINT
        if all_embeddings:
            try:
                await self.batch_upload_qdrant(all_embeddings)
            except Exception as e:
                logger.error(f"CRITICAL: Batch upload failed, cannot continue: {e}")
                raise  # This will stop the entire processing

        return len(all_embeddings)

    async def batch_upload_qdrant(self, embeddings_data: List[Dict[str, Any]]):
        """Ultra-fast batch upload to Qdrant with fail-fast behavior"""
        try:
            import hashlib
            import uuid
            from qdrant_client.models import PointStruct

            points = []
            for data in embeddings_data:
                try:
                    product = data['product']
                    image_emb = data['image_emb'].flatten()
                    text_emb = data['text_emb'].flatten()
                    combined_emb = np.concatenate([image_emb, text_emb])

                    # Fast UUID generation
                    point_id = str(uuid.uuid4())

                    points.append(PointStruct(
                        id=point_id,
                        vector={
                            "image": image_emb.tolist(),
                            "text": text_emb.tolist(),
                            "combined": combined_emb.tolist()
                        },
                        payload={
                            "product_id": product['id'],
                            "title": product['title'],
                            "image_url": product['image_url'],
                            "model_used": "Marqo/marqo-fashionSigLIP",
                            "timestamp": datetime.now().isoformat()
                        }
                    ))
                except Exception as pe:
                    logger.warning(f"Point creation failed for product: {pe}")
                    continue

            # Single massive upload - CRITICAL FAILURE POINT
            if points:
                try:
                    logger.info(f"Uploading {len(points)} embeddings to Qdrant...")
                    self.qdrant_client.upsert(collection_name=self.collection_name, points=points)
                    logger.info(f"Successfully uploaded {len(points)} embeddings")
                except Exception as ue:
                    logger.error(f"CRITICAL: Qdrant upload failed: {ue}")
                    logger.error(f"STOPPING PROCESSING - No point continuing without storage")
                    raise RuntimeError(f"Qdrant upload failed: {ue}")
            else:
                logger.warning("No points created for upload")

        except Exception as e:
            if "CRITICAL" in str(e):
                raise  # Re-raise critical errors to stop processing
            logger.error(f"Upload failed: {e}")
            raise RuntimeError(f"Batch upload failed: {e}")

    async def run_extreme_mode(self, target_products: int = 6_000_000):
        """EXTREME MODE: 2-day processing"""
        required_rate = target_products / (48 * 60)  # products per minute for 48 hours

        logger.info(f"EXTREME MODE ACTIVATED")
        logger.info(f"Target: {target_products:,} products in 48 hours")
        logger.info(f"Required rate: {required_rate:.0f} products/minute")
        logger.info(f"Batch: {self.batch_size:,}, Concurrent: {self.max_concurrent}, Workers: {self.num_workers}")

        self.load_checkpoint()
        if not self.stats['start_time']:
            self.stats['start_time'] = datetime.now().isoformat()

        if not await self.initialize_model():
            return False

        batch_count = 0
        start_time = time.time()

        try:
            while self.stats['total_processed'] < target_products:
                batch_count += 1
                batch_start = time.time()

                logger.info(f"EXTREME BATCH {batch_count} (processed: {self.stats['total_processed']:,})")

                # Get massive batch
                products = await self.get_massive_batch()
                if not products:
                    break

                # Download with maximum parallelism
                downloaded_products = await self.download_massive_batch(products)

                # Process with multiple workers
                successful = await self.process_with_workers(downloaded_products)

                # Update stats
                self.stats['total_processed'] += len(products)
                self.stats['successful'] += successful

                # Performance metrics
                batch_time = time.time() - batch_start
                total_time = time.time() - start_time
                current_rate = len(products) / batch_time * 60
                overall_rate = self.stats['total_processed'] / total_time * 60

                # ETA
                remaining = target_products - self.stats['total_processed']
                eta_hours = remaining / overall_rate / 60 if overall_rate > 0 else 0

                progress_pct = self.stats['total_processed'] / target_products * 100

                logger.info(f"EXTREME STATS:")
                logger.info(f"   Progress: {self.stats['total_processed']:,}/{target_products:,} ({progress_pct:.1f}%)")
                logger.info(f"   Rate: {current_rate:.0f}/min (overall: {overall_rate:.0f}/min)")
                logger.info(f"   ETA: {eta_hours:.1f}h ({eta_hours/24:.1f} days)")
                logger.info(f"   Target Rate: {required_rate:.0f}/min {'OK' if overall_rate >= required_rate else 'BELOW TARGET'}")

                # Checkpoint every 3 batches (less frequent for speed)
                if batch_count % 3 == 0:
                    self.save_checkpoint()

                # Minimal delay
                await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("EXTREME processing interrupted")
        except Exception as e:
            logger.error(f"EXTREME processing failed: {e}")
        finally:
            self.save_checkpoint()
            total_time = time.time() - start_time
            final_rate = self.stats['successful'] / (total_time / 60) if total_time > 0 else 0

            logger.info(f"EXTREME FINAL:")
            logger.info(f"   Processed: {self.stats['total_processed']:,}")
            logger.info(f"   Successful: {self.stats['successful']:,}")
            logger.info(f"   Final Rate: {final_rate:.0f}/min")
            logger.info(f"   Time: {total_time/3600:.1f}h")

        return self.stats['successful'] > 0

async def main():
    processor = ExtremeFashionSigProcessor()
    target = int(os.getenv('TARGET_PRODUCTS', '6000000'))
    return await processor.run_extreme_mode(target)

if __name__ == "__main__":
    # Set process limits
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_NOFILE, (65536, 65536))  # Max file descriptors
    except:
        pass

    success = asyncio.run(main())
    sys.exit(0 if success else 1)