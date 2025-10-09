#!/usr/bin/env python3
"""
Precompute FashionSigLIP Embeddings for All Products

This script processes all products from Neo4j, generates multimodal embeddings
using Marqo/marqo-fashionSigLIP, and stores them in a separate Qdrant collection.

Usage:
    python scripts/precompute_fashion_embeddings.py [--batch-size 32] [--gpu-memory-limit 0.8]
"""

import os
import sys
import asyncio
import logging
import argparse
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import json
import hashlib

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/embedding_precomputation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("precompute_embeddings")

# Try to import required libraries
try:
    import torch
    from transformers import AutoModel, AutoProcessor
    from PIL import Image
    import numpy as np
    import requests
    from io import BytesIO
    TRANSFORMERS_AVAILABLE = True
except ImportError as e:
    logger.error(f"Required libraries not available: {e}")
    logger.error("Install with: pip install transformers torch pillow requests")
    sys.exit(1)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    QDRANT_AVAILABLE = True
    logger.info("Qdrant client imported successfully")
except ImportError:
    QDRANT_AVAILABLE = False
    logger.error("Qdrant client required: pip install qdrant-client")
    # Define dummy classes for type hints when imports fail
    class QdrantClient: pass
    class Distance: pass
    class VectorParams: pass
    class PointStruct: pass
    class Filter: pass
    class FieldCondition: pass
    class MatchValue: pass

# Import project modules
from services.user.knowledge_graph import UserKnowledgeGraphService
from services.ml.intelligence.visual_pytorch import DEFAULT_ALLOWED_DOMAINS, MAX_IMAGE_SIZE, REQUEST_TIMEOUT


class FashionEmbeddingPrecomputer:
    """
    Precomputes and stores FashionSigLIP embeddings for all products.
    """

    def __init__(
        self,
        neo4j_service: UserKnowledgeGraphService,
        qdrant_client: QdrantClient,
        model_name: str = 'Marqo/marqo-fashionSigLIP',
        collection_name: str = 'fashion_multimodal_embeddings',
        batch_size: int = 32,
        device: str = 'auto',
        gpu_memory_limit: float = 0.8,
        fusion_strategy: str = 'concatenate'
    ):
        """
        Initialize the precomputer.

        Args:
            neo4j_service: Neo4j service for fetching products
            qdrant_client: Qdrant client for storing embeddings
            model_name: HuggingFace model name
            collection_name: Qdrant collection name
            batch_size: Processing batch size
            device: Device to use ('auto', 'cpu', 'cuda')
            gpu_memory_limit: GPU memory threshold for cleanup
            fusion_strategy: How to combine image+text embeddings
        """
        self.neo4j = neo4j_service
        self.qdrant = qdrant_client
        self.model_name = model_name
        self.collection_name = collection_name
        self.batch_size = batch_size
        self.fusion_strategy = fusion_strategy
        self.gpu_memory_limit = gpu_memory_limit

        # Device setup
        if device == 'auto':
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)

        logger.info(f"Using device: {self.device}")

        # Initialize model and processor
        self.model = None
        self.processor = None
        self.embedding_dim = 512  # Default

        # Statistics
        self.stats = {
            "total_products": 0,
            "processed_products": 0,
            "successful_embeddings": 0,
            "failed_embeddings": 0,
            "skipped_existing": 0,
            "image_embeddings": 0,
            "text_embeddings": 0,
            "combined_embeddings": 0,
            "processing_time": 0.0,
            "start_time": None
        }

        # Security - reuse allowed domains
        self.allowed_domains = DEFAULT_ALLOWED_DOMAINS

    async def initialize(self):
        """Initialize models and Qdrant collection."""
        logger.info("Initializing FashionSigLIP model...")

        try:
            # Load processor and model
            self.processor = AutoProcessor.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )

            self.model = AutoModel.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )

            # Move to device and set eval mode
            self.model = self.model.to(self.device)
            self.model.eval()

            # Disable gradients
            for param in self.model.parameters():
                param.requires_grad = False

            # Get embedding dimension
            if hasattr(self.model.config, 'projection_dim'):
                self.embedding_dim = self.model.config.projection_dim
            elif hasattr(self.model.config, 'hidden_size'):
                self.embedding_dim = self.model.config.hidden_size
            else:
                self.embedding_dim = 512

            logger.info(f"Model loaded successfully (embedding_dim={self.embedding_dim})")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

        # Initialize Qdrant collection
        await self._setup_qdrant_collection()

    async def _setup_qdrant_collection(self):
        """Setup Qdrant collection for multimodal embeddings."""
        try:
            # Calculate combined embedding dimension based on fusion strategy
            if self.fusion_strategy == 'concatenate':
                combined_dim = self.embedding_dim * 2  # image + text
            else:
                combined_dim = self.embedding_dim  # same size for average/weighted

            # Check if collection exists
            collections = self.qdrant.get_collections().collections
            collection_exists = any(c.name == self.collection_name for c in collections)

            if not collection_exists:
                logger.info(f"Creating Qdrant collection: {self.collection_name}")

                # Create collection with vector configurations
                self.qdrant.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "image": VectorParams(
                            size=self.embedding_dim,
                            distance=Distance.COSINE
                        ),
                        "text": VectorParams(
                            size=self.embedding_dim,
                            distance=Distance.COSINE
                        ),
                        "combined": VectorParams(
                            size=combined_dim,
                            distance=Distance.COSINE
                        )
                    }
                )
                logger.info("Qdrant collection created successfully")
            else:
                logger.info(f"Qdrant collection {self.collection_name} already exists")

        except Exception as e:
            logger.error(f"Failed to setup Qdrant collection: {e}")
            raise

    async def precompute_all_embeddings(self, resume: bool = True, limit: Optional[int] = None):
        """
        Precompute embeddings for all products in the graph.

        Args:
            resume: Whether to skip products that already have embeddings
            limit: Maximum number of products to process (for testing)
        """
        self.stats["start_time"] = datetime.now()
        logger.info("Starting embedding precomputation...")

        try:
            # Get all products from Neo4j
            products = await self._fetch_all_products(limit=limit)
            self.stats["total_products"] = len(products)

            logger.info(f"Found {len(products)} products to process")

            # Process in batches
            for i in range(0, len(products), self.batch_size):
                batch = products[i:i + self.batch_size]
                batch_start = time.time()

                logger.info(f"Processing batch {i//self.batch_size + 1}/{(len(products)-1)//self.batch_size + 1} "
                           f"(products {i+1}-{min(i+self.batch_size, len(products))})")

                # Check if we should skip existing embeddings
                if resume:
                    batch = await self._filter_existing_embeddings(batch)

                if not batch:
                    logger.info("All products in batch already processed, skipping...")
                    continue

                # Process batch
                await self._process_batch(batch)

                # GPU memory management
                if self.device.type == 'cuda':
                    self._cleanup_gpu_memory()

                batch_time = time.time() - batch_start
                logger.info(f"Batch completed in {batch_time:.2f}s")

                # Progress update
                self._log_progress()

        except Exception as e:
            logger.error(f"Error in precomputation: {e}")
            raise
        finally:
            self._log_final_stats()

    async def _fetch_all_products(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch all products from Neo4j."""
        try:
            query = """
            MATCH (p:Product)
            WHERE p.id IS NOT NULL
            RETURN p.id as id, p.title as title, p.description as description,
                   p.categories as categories, p.tags as tags, p.brand as brand,
                   p.color as color, p.material as material, p.images as images,
                   p.price as price
            ORDER BY p.id
            """

            if limit:
                query += f" LIMIT {limit}"

            result = await self.neo4j.query(query)
            return [dict(record) for record in result]

        except Exception as e:
            logger.error(f"Failed to fetch products from Neo4j: {e}")
            raise

    async def _filter_existing_embeddings(self, batch: List[Dict]) -> List[Dict]:
        """Filter out products that already have embeddings."""
        try:
            # Get UUIDs from batch
            uuids = [p['id'] for p in batch]

            # Check which ones exist in Qdrant
            existing_points = []
            for uuid in uuids:
                try:
                    point = self.qdrant.retrieve(
                        collection_name=self.collection_name,
                        ids=[uuid]
                    )
                    if point:
                        existing_points.append(uuid)
                except:
                    # Point doesn't exist
                    pass

            # Filter out existing
            filtered_batch = [p for p in batch if p['id'] not in existing_points]

            self.stats["skipped_existing"] += len(existing_points)

            if existing_points:
                logger.info(f"Skipping {len(existing_points)} products with existing embeddings")

            return filtered_batch

        except Exception as e:
            logger.warning(f"Error filtering existing embeddings: {e}")
            return batch  # Return full batch if filtering fails

    async def _process_batch(self, batch: List[Dict]):
        """Process a batch of products."""
        for product in batch:
            try:
                await self._process_single_product(product)
                self.stats["processed_products"] += 1

            except Exception as e:
                logger.error(f"Failed to process product {product.get('id')}: {e}")
                self.stats["failed_embeddings"] += 1

    async def _process_single_product(self, product: Dict[str, Any]):
        """Process a single product to generate and store embeddings."""
        product_id = product['id']

        try:
            # Extract text content
            text_content = self._extract_product_text(product)

            # Get and validate images
            valid_images = await self._get_valid_images(product)

            # Generate embeddings
            embeddings = await self._generate_embeddings(text_content, valid_images)

            if not embeddings:
                raise ValueError("Failed to generate embeddings")

            # Store in Qdrant
            await self._store_embeddings(product_id, embeddings, product)

            self.stats["successful_embeddings"] += 1

        except Exception as e:
            logger.error(f"Error processing product {product_id}: {e}")
            raise

    def _extract_product_text(self, product: Dict[str, Any]) -> str:
        """Extract comprehensive text from product."""
        text_parts = []

        # Core fields
        for field in ['title', 'description', 'brand', 'color', 'material']:
            if product.get(field):
                text_parts.append(str(product[field]))

        # Lists
        for field in ['categories', 'tags']:
            items = product.get(field, [])
            if isinstance(items, list):
                text_parts.extend(items)
            elif isinstance(items, str):
                text_parts.append(items)

        return " ".join(filter(None, text_parts))

    async def _get_valid_images(self, product: Dict[str, Any]) -> List[Image.Image]:
        """Get valid images from product."""
        valid_images = []

        images = product.get('images', [])
        if isinstance(images, str):
            images = [images]

        for img_url in images[:3]:  # Limit to 3 images
            try:
                image_data = await self._download_image_safely(img_url)
                if image_data:
                    img = Image.open(BytesIO(image_data)).convert('RGB')

                    # Validate dimensions
                    if (32 <= img.width <= 4096 and 32 <= img.height <= 4096):
                        valid_images.append(img)

            except Exception as e:
                logger.warning(f"Failed to process image {img_url}: {e}")
                continue

        return valid_images

    async def _download_image_safely(self, url: str) -> Optional[bytes]:
        """Download image with security validation."""
        try:
            # Validate URL
            if not self._validate_image_url(url):
                return None

            # Download with timeout
            response = await asyncio.to_thread(
                requests.get,
                url,
                timeout=REQUEST_TIMEOUT,
                headers={'User-Agent': 'ARI-FashionBot/1.0'}
            )

            response.raise_for_status()

            # Check size
            if len(response.content) > MAX_IMAGE_SIZE:
                logger.warning(f"Image too large: {len(response.content)} bytes")
                return None

            return response.content

        except Exception as e:
            logger.warning(f"Failed to download image {url}: {e}")
            return None

    def _validate_image_url(self, url: str) -> bool:
        """Validate image URL for security."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)

            if parsed.scheme not in ['http', 'https']:
                return False

            domain = parsed.netloc.lower()
            if ':' in domain:
                domain = domain.split(':')[0]

            # Check allowed domains
            for allowed in self.allowed_domains:
                if domain == allowed or domain.endswith(f'.{allowed}'):
                    return True

            return False

        except:
            return False

    async def _generate_embeddings(
        self,
        text: str,
        images: List[Image.Image]
    ) -> Optional[Dict[str, List[float]]]:
        """Generate FashionSigLIP embeddings."""
        try:
            embeddings = {}

            # Generate text embedding
            if text:
                text_inputs = self.processor(
                    text=[text],
                    return_tensors="pt",
                    padding=True,
                    truncation=True
                ).to(self.device)

                with torch.no_grad():
                    text_features = self.model.get_text_features(
                        text_inputs['input_ids'], normalize=True
                    )
                    embeddings['text'] = text_features.cpu().numpy().flatten().tolist()
                    self.stats["text_embeddings"] += 1

            # Generate image embeddings (average multiple images)
            if images:
                image_embeddings = []

                for img in images:
                    img_inputs = self.processor(
                        images=[img],
                        return_tensors="pt"
                    ).to(self.device)

                    with torch.no_grad():
                        img_features = self.model.get_image_features(
                            img_inputs['pixel_values'], normalize=True
                        )
                        image_embeddings.append(img_features.cpu().numpy().flatten())

                # Average multiple images
                if image_embeddings:
                    avg_embedding = np.mean(image_embeddings, axis=0)
                    embeddings['image'] = avg_embedding.tolist()
                    self.stats["image_embeddings"] += 1

            # Generate combined embedding
            if 'text' in embeddings and 'image' in embeddings:
                combined = self._fuse_embeddings(embeddings['text'], embeddings['image'])
                embeddings['combined'] = combined
                self.stats["combined_embeddings"] += 1
            elif 'text' in embeddings:
                embeddings['combined'] = embeddings['text']
            elif 'image' in embeddings:
                embeddings['combined'] = embeddings['image']

            return embeddings if embeddings else None

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return None

    def _fuse_embeddings(self, text_emb: List[float], image_emb: List[float]) -> List[float]:
        """Fuse text and image embeddings."""
        text_arr = np.array(text_emb)
        image_arr = np.array(image_emb)

        if self.fusion_strategy == 'concatenate':
            return np.concatenate([image_arr, text_arr]).tolist()
        elif self.fusion_strategy == 'average':
            return ((image_arr + text_arr) / 2).tolist()
        elif self.fusion_strategy == 'weighted':
            return (0.6 * image_arr + 0.4 * text_arr).tolist()
        else:
            return np.concatenate([image_arr, text_arr]).tolist()

    async def _store_embeddings(
        self,
        product_id: str,
        embeddings: Dict[str, List[float]],
        product: Dict[str, Any]
    ):
        """Store embeddings in Qdrant."""
        try:
            # Prepare payload
            payload = {
                "product_id": product_id,
                "title": product.get('title', ''),
                "categories": product.get('categories', []),
                "brand": product.get('brand', ''),
                "color": product.get('color', ''),
                "price": product.get('price', 0),
                "has_image": 'image' in embeddings,
                "has_text": 'text' in embeddings,
                "embedding_strategy": self.fusion_strategy,
                "processed_at": datetime.now().isoformat()
            }

            # Create point with multiple vectors
            point = PointStruct(
                id=product_id,  # Use product UUID as point ID
                payload=payload,
                vector={
                    "image": embeddings.get('image', [0.0] * self.embedding_dim),
                    "text": embeddings.get('text', [0.0] * self.embedding_dim),
                    "combined": embeddings.get('combined', [0.0] * len(embeddings.get('combined', [])))
                }
            )

            # Store in Qdrant
            self.qdrant.upsert(
                collection_name=self.collection_name,
                points=[point]
            )

        except Exception as e:
            logger.error(f"Failed to store embeddings for {product_id}: {e}")
            raise

    def _cleanup_gpu_memory(self):
        """Clean up GPU memory."""
        if self.device.type == 'cuda':
            torch.cuda.empty_cache()

            # Check memory usage
            allocated = torch.cuda.memory_allocated()
            total = torch.cuda.get_device_properties(0).total_memory

            if allocated / total > self.gpu_memory_limit:
                logger.warning(f"GPU memory usage high: {allocated/total:.1%}")
                torch.cuda.empty_cache()

    def _log_progress(self):
        """Log current progress."""
        elapsed = (datetime.now() - self.stats["start_time"]).total_seconds()
        self.stats["processing_time"] = elapsed

        processed = self.stats["processed_products"]
        total = self.stats["total_products"]

        if processed > 0:
            rate = processed / elapsed
            eta = (total - processed) / rate if rate > 0 else 0

            logger.info(f"Progress: {processed}/{total} ({processed/total*100:.1f}%) "
                       f"- Rate: {rate:.1f} products/sec - ETA: {eta/60:.1f}min")

    def _log_final_stats(self):
        """Log final statistics."""
        stats = self.stats
        elapsed = stats["processing_time"]

        logger.info("=== EMBEDDING PRECOMPUTATION COMPLETE ===")
        logger.info(f"Total products: {stats['total_products']}")
        logger.info(f"Processed: {stats['processed_products']}")
        logger.info(f"Successful: {stats['successful_embeddings']}")
        logger.info(f"Failed: {stats['failed_embeddings']}")
        logger.info(f"Skipped existing: {stats['skipped_existing']}")
        logger.info(f"Image embeddings: {stats['image_embeddings']}")
        logger.info(f"Text embeddings: {stats['text_embeddings']}")
        logger.info(f"Combined embeddings: {stats['combined_embeddings']}")
        logger.info(f"Total time: {elapsed/60:.1f} minutes")

        if stats['processed_products'] > 0:
            rate = stats['processed_products'] / elapsed
            logger.info(f"Average rate: {rate:.1f} products/second")


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Precompute FashionSigLIP embeddings')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size for processing')
    parser.add_argument('--gpu-memory-limit', type=float, default=0.8, help='GPU memory threshold')
    parser.add_argument('--model', default='Marqo/marqo-fashionSigLIP', help='Model name')
    parser.add_argument('--collection', default='fashion_multimodal_embeddings', help='Qdrant collection')
    parser.add_argument('--fusion-strategy', choices=['concatenate', 'average', 'weighted'],
                       default='concatenate', help='Embedding fusion strategy')
    parser.add_argument('--no-resume', action='store_true', help='Don\'t skip existing embeddings')
    parser.add_argument('--device', choices=['auto', 'cpu', 'cuda'], default='auto', help='Device to use')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of products to process for testing')

    args = parser.parse_args()

    # Check dependencies after parsing args (so help can work)
    if not QDRANT_AVAILABLE:
        logger.error("Qdrant client not available. Install with: pip install qdrant-client")
        sys.exit(1)

    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    # Initialize services
    try:
        # Neo4j
        neo4j_service = UserKnowledgeGraphService(
            uri=os.getenv("NEO4J_URL", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "")
        )
        await neo4j_service.initialize()

        # Qdrant
        qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY")
        )

        # Create precomputer
        precomputer = FashionEmbeddingPrecomputer(
            neo4j_service=neo4j_service,
            qdrant_client=qdrant_client,
            model_name=args.model,
            collection_name=args.collection,
            batch_size=args.batch_size,
            device=args.device,
            gpu_memory_limit=args.gpu_memory_limit,
            fusion_strategy=args.fusion_strategy
        )

        # Initialize and run
        await precomputer.initialize()
        await precomputer.precompute_all_embeddings(resume=not args.no_resume, limit=args.limit)

    except Exception as e:
        logger.error(f"Error in main: {e}")
        sys.exit(1)
    finally:
        if 'neo4j_service' in locals():
            await neo4j_service.close()


if __name__ == "__main__":
    asyncio.run(main())