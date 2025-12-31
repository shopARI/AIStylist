#!/usr/bin/env python3
"""
FashionSigLIP Batch Precomputation - Optimized for 6M Products on A100
Processes 512 products in parallel batches for maximum efficiency
"""

import os
import sys
import asyncio
import logging
import requests
import numpy as np
import torch
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import time
from datetime import datetime
import uuid
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import aiohttp
from io import BytesIO

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Enable debug logging to see URL processing
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fashionsig_batch")

def load_environment():
    """Load environment variables"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("Environment loaded")
    except ImportError:
        logger.warning("python-dotenv not available, using OS environment")

async def test_neo4j_connection():
    """Test Neo4j connection and fetch products"""
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URL", "bolt://localhost:7687"),
            auth=(
                os.getenv("NEO4J_USERNAME", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "")
            )
        )

        # Test connection
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            result.single()

        logger.info("Neo4j connection successful")
        return driver

    except Exception as e:
        logger.error(f"Neo4j connection failed: {e}")
        return None

async def fetch_products_batch(driver, offset: int = 0, batch_size: int = 512):
    """Fetch products in batches from Neo4j"""
    query = """
    MATCH (p:Product)
    WHERE p.id IS NOT NULL AND p.images IS NOT NULL
    RETURN p.id as id, p.title as title, p.images as images,
           p.description as description
    ORDER BY p.id
    SKIP $offset
    LIMIT $batch_size
    """

    try:
        with driver.session() as session:
            result = session.run(query, {"offset": offset, "batch_size": batch_size})
            products = [record.data() for record in result]
            logger.info(f"Fetched {len(products)} products (offset: {offset})")
            return products
    except Exception as e:
        logger.error(f"Failed to fetch products: {e}")
        return []

def setup_fashionsig_batch():
    """Initialize FashionSigLIP for batch processing"""
    try:
        import torch
        from transformers import AutoProcessor, AutoModel
        from PIL import Image

        logger.info("Loading FashionSigLIP for batch processing...")

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Device: {device}")

        # Load FashionSigLIP model
        local_model_path = "/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/marqo-fashionSigLIP"

        # Load processor
        processor = AutoProcessor.from_pretrained(
            local_model_path,
            trust_remote_code=True,
            local_files_only=True
        )
        logger.info("Processor loaded")

        # Load model
        logger.info("Loading model from local files...")
        model = AutoModel.from_pretrained(
            local_model_path,
            trust_remote_code=True,
            local_files_only=True,
            low_cpu_mem_usage=False
        )

        logger.info("Moving model to device...")
        model = model.to(device)
        model.eval()  # Set to evaluation mode
        logger.info("Model loaded successfully")

        return model, processor, device, torch, np

    except Exception as e:
        logger.error(f"FashionSigLIP batch setup failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None, None

def setup_qdrant_batch():
    """Initialize Qdrant client for batch operations"""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        client = QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY"),
            prefer_grpc=False
        )

        collections = client.get_collections().collections
        logger.info(f"Qdrant connected ({len(collections)} collections)")

        return client, VectorParams, Distance

    except Exception as e:
        logger.error(f"Qdrant batch setup failed: {e}")
        return None, None, None

async def download_image_batch(session, img_path: str, timeout: int = 10):
    """Download single image asynchronously with proper URL formatting"""
    try:
        # Convert all URLs to internal app.shopari.com format
        if not img_path.startswith(('http://', 'https://')):
            # Relative path - add prefix
            img_url = f"https://app.shopari.com/images/{img_path}"
        elif 'shopify.com' in img_path or 'cdn.' in img_path:
            # Skip old Shopify URLs - these need to be updated in the database
            # to use the full directory path structure
            logger.debug(f"Skipping Shopify URL (needs database update): {img_path}")
            return None, img_path
        else:
            # Already correct URL format
            img_url = img_path

        async with session.get(img_url, timeout=timeout) as response:
            if response.status == 200:
                content = await response.read()
                content_type = response.headers.get('content-type', 'unknown')
                content_length = len(content)

                # Debug what we actually downloaded
                logger.debug(f"Downloaded {content_length} bytes, content-type: {content_type}")

                # Check if content looks like an image
                if content_length < 100:
                    logger.warning(f"Downloaded content too small ({content_length} bytes): {img_url}")
                    return None, img_url

                if not content_type.startswith('image/'):
                    logger.warning(f"Non-image content-type '{content_type}': {img_url}")
                    # Log first 200 chars to see what we got
                    preview = content[:200].decode('utf-8', errors='ignore')
                    logger.warning(f"HTML content preview: {preview[:150]}...")
                    return None, img_url

                from PIL import Image
                try:
                    img = Image.open(BytesIO(content)).convert('RGB')
                    return img, img_url
                except Exception as img_error:
                    logger.warning(f"PIL cannot open image {img_url}: {img_error}")
                    return None, img_url
            else:
                logger.warning(f"Failed to download {img_url}: {response.status}")
                return None, img_url

    except Exception as e:
        logger.warning(f"Image download error {img_url}: {e}")
        return None, img_url

async def process_batch_fashionsig(
    products_batch: List[Dict],
    model, processor, device, torch, np,
    qdrant_client,
    session: aiohttp.ClientSession
):
    """Process a batch of products with FashionSigLIP"""
    batch_results = []
    collection_name = "fashion_fashionsig_768d"

    logger.info(f"Processing batch of {len(products_batch)} products...")

    # Prepare all images and texts
    batch_images = []
    batch_texts = []
    batch_metadata = []

    # Download all images in parallel
    download_tasks = []
    for product in products_batch:
        # Prepare text
        text_content = []
        for field in ['title', 'description']:
            if product.get(field):
                text_content.append(str(product[field]))

        full_text = " ".join(filter(None, text_content))
        text_words = full_text.split()[:40]  # Limit for token constraints
        text = " ".join(text_words)

        # Process images
        images_data = product.get('images', [])
        if isinstance(images_data, str):
            try:
                images_data = json.loads(images_data)
            except:
                images_data = [images_data]

        # Take first image for now
        if images_data:
            img_url = images_data[0]
            logger.debug(f"Search Raw image URL from Neo4j: {img_url}")
            download_tasks.append(download_image_batch(session, img_url))
            batch_texts.append(text)
            batch_metadata.append({
                "product_id": product['id'],
                "title": product['title'],
                "text_content": text,
                "image_url": img_url,
                "image_index": 0
            })

    # Execute all downloads
    download_results = await asyncio.gather(*download_tasks, return_exceptions=True)

    # Filter successful downloads
    valid_items = []
    for i, (img_result, meta) in enumerate(zip(download_results, batch_metadata)):
        if isinstance(img_result, tuple) and img_result[0] is not None:
            img, img_url = img_result
            valid_items.append({
                "image": img,
                "text": batch_texts[i],
                "metadata": meta
            })

    if not valid_items:
        logger.warning("No valid images in batch")
        return batch_results

    logger.info(f"Processing {len(valid_items)} valid images in batch...")

    # Prepare batch inputs
    images = [item["image"] for item in valid_items]
    texts = [item["text"] for item in valid_items]

    try:
        # Process entire batch at once
        with torch.no_grad():
            # FashionSigLIP batch processing
            inputs = processor(
                text=texts,
                images=images,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=64  # SigLIP uses 64
            )

            # Remove attention_mask for MarqoFashionSigLIP compatibility
            if 'attention_mask' in inputs:
                del inputs['attention_mask']

            # Move to device
            inputs = {k: v.to(device) for k, v in inputs.items()}

            # Generate embeddings
            outputs = model(**inputs)

            # Handle MarqoFashionSigLIP output format (tuple with 4 tensors)
            if isinstance(outputs, tuple) and len(outputs) == 4:
                image_embeddings = outputs[2].cpu().numpy()  # Shape: (batch_size, 768)
                text_embeddings = outputs[3].cpu().numpy()   # Shape: (batch_size, 768)
            else:
                logger.error("Unexpected model output format")
                return batch_results

        logger.info(f"Generated embeddings: images {image_embeddings.shape}, texts {text_embeddings.shape}")

        # Prepare batch upload to Qdrant
        if qdrant_client:
            points_batch = []

            for i, item in enumerate(valid_items):
                # Get embeddings for this item
                image_embedding = image_embeddings[i]  # 768-dim
                text_embedding = text_embeddings[i]    # 768-dim
                combined_embedding = np.concatenate([image_embedding, text_embedding])  # 1536-dim

                # Create point ID
                unique_string = f"{item['metadata']['product_id']}_img_{item['metadata']['image_index']}"
                hash_object = hashlib.md5(unique_string.encode())
                point_id = str(uuid.UUID(hash_object.hexdigest()))

                # Create Qdrant point
                from qdrant_client.models import PointStruct

                point = PointStruct(
                    id=point_id,
                    vector={
                        "image": image_embedding.tolist(),
                        "text": text_embedding.tolist(),
                        "combined": combined_embedding.tolist()
                    },
                    payload={
                        "product_id": item['metadata']['product_id'],
                        "title": item['metadata']['title'][:200],
                        "text_content": item['metadata']['text_content'][:200],
                        "image_url": item['metadata']['image_url'],
                        "image_size": f"{item['image'].size[0]}x{item['image'].size[1]}",
                        "model_used": "marqo_fashionsig",
                        "embedding_dims": len(image_embedding),
                        "timestamp": datetime.now().isoformat(),
                        "approach": "batch_fashionsig"
                    }
                )
                points_batch.append(point)

                # Track result
                batch_results.append({
                    "product_id": item['metadata']['product_id'],
                    "title": item['metadata']['title'],
                    "status": "success",
                    "embeddings_created": 1,
                    "qdrant_uploaded": True,
                    "point_id": point_id
                })

            # Batch upload to Qdrant
            if points_batch:
                try:
                    qdrant_client.upsert(
                        collection_name=collection_name,
                        points=points_batch
                    )
                    logger.info(f"Batch uploaded {len(points_batch)} points to Qdrant")
                except Exception as upload_error:
                    logger.error(f"Batch Qdrant upload failed: {upload_error}")
                    # Update results to reflect failed upload
                    for result in batch_results:
                        result["qdrant_uploaded"] = False

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        import traceback
        traceback.print_exc()

    return batch_results

async def main():
    """Main batch processing function"""
    import argparse

    parser = argparse.ArgumentParser(description='FashionSigLIP Batch Precomputation')
    parser.add_argument('--limit', type=int, default=10000000, help='Total number of products to process')
    parser.add_argument('--batch_size', type=int, default=512, help='Batch size for processing')
    parser.add_argument('--offset', type=int, default=0, help='Starting offset')
    args = parser.parse_args()

    logger.info(f"Starting FashionSigLIP BATCH precomputation")
    logger.info(f"   Limit: {args.limit}, Batch size: {args.batch_size}, Offset: {args.offset}")

    # Load environment
    load_environment()

    # Setup connections
    neo4j_driver = await test_neo4j_connection()
    if not neo4j_driver:
        return

    # Setup FashionSigLIP
    model, processor, device, torch, np = setup_fashionsig_batch()
    if not model:
        return

    # Setup Qdrant
    qdrant_client, _, _ = setup_qdrant_batch()

    # Process in batches
    total_processed = 0
    total_successful = 0
    all_results = []

    start_time = time.time()

    async with aiohttp.ClientSession() as session:
        current_offset = args.offset

        while total_processed < args.limit:
            # Calculate current batch size
            remaining = args.limit - total_processed
            current_batch_size = min(args.batch_size, remaining)

            logger.info(f"Processing batch {total_processed // args.batch_size + 1}")
            logger.info(f"   Offset: {current_offset}, Batch size: {current_batch_size}")

            # Fetch products for this batch
            products_batch = await fetch_products_batch(neo4j_driver, current_offset, current_batch_size)

            if not products_batch:
                logger.info("No more products to process")
                break

            # Process this batch
            batch_results = await process_batch_fashionsig(
                products_batch, model, processor, device, torch, np, qdrant_client, session
            )

            # Update counters
            total_processed += len(products_batch)
            batch_successful = len([r for r in batch_results if r.get("status") == "success"])
            total_successful += batch_successful

            all_results.extend(batch_results)

            # Progress report
            elapsed = time.time() - start_time
            rate = total_processed / elapsed if elapsed > 0 else 0
            eta_seconds = (args.limit - total_processed) / rate if rate > 0 else 0
            eta_hours = eta_seconds / 3600

            logger.info(f"Batch completed: {batch_successful}/{len(products_batch)} successful")
            logger.info(f"Total progress: {total_processed}/{args.limit} ({total_processed/args.limit*100:.1f}%)")
            logger.info(f"Processing rate: {rate:.1f} products/sec")
            logger.info(f"ETA: {eta_hours:.1f} hours")
            logger.info("-" * 60)

            current_offset += current_batch_size

            # Small delay to prevent overwhelming the system
            await asyncio.sleep(1)

    # Save final results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"fashionsig_batch_{args.batch_size}_{total_processed}_{timestamp}.json"

    total_embeddings = sum(r.get("embeddings_created", 0) for r in all_results)
    upload_successful = len([r for r in all_results if r.get("qdrant_uploaded", False)])

    summary = {
        "timestamp": timestamp,
        "model_used": "marqo_fashionsig_batch",
        "batch_size": args.batch_size,
        "total_processed": total_processed,
        "successful_products": total_successful,
        "total_embeddings": total_embeddings,
        "qdrant_uploads": upload_successful,
        "upload_rate": f"{upload_successful/total_processed*100:.1f}%" if total_processed > 0 else "0%",
        "processing_time": time.time() - start_time,
        "products_per_second": total_processed / (time.time() - start_time) if (time.time() - start_time) > 0 else 0,
        "approach": "batch_fashionsig",
        "results": all_results
    }

    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Results saved to: {output_file}")
    logger.info(f"BATCH PROCESSING COMPLETED!")
    logger.info(f"Final Summary:")
    logger.info(f"   Products: {total_successful}/{total_processed}")
    logger.info(f"   Embeddings: {total_embeddings}")
    logger.info(f"   Qdrant uploads: {upload_successful}")
    logger.info(f"   Upload rate: {upload_successful/total_processed*100:.1f}%" if total_processed > 0 else "0%")
    logger.info(f"   Processing rate: {total_processed / (time.time() - start_time):.1f} products/sec")

    neo4j_driver.close()

if __name__ == "__main__":
    asyncio.run(main())