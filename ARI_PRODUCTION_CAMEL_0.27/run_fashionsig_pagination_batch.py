#!/usr/bin/env python3
"""
FashionSigLIP Batch Processing with Proper Pagination
Ensures unique products across batches using SKIP/LIMIT
"""

import os
import sys
import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fashionsig_pagination")

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

async def get_unique_products_batch(skip_count: int = 0, batch_size: int = 512):
    """Get a unique batch of products with pagination"""
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URL", "bolt://localhost:7687"),
            auth=(
                os.getenv("NEO4J_USERNAME", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "")
            )
        )

        logger.info(f"Fetching products {skip_count:,} to {skip_count + batch_size:,}")

        with driver.session() as session:
            # Use SKIP for pagination to get truly unique batches
            result = session.run(f"""
                MATCH (p:Product)
                WHERE p.images IS NOT NULL
                RETURN p.id, p.title, p.images
                ORDER BY p.id  // Ensure consistent ordering
                SKIP {skip_count}
                LIMIT {batch_size}
            """)

            successful_urls = []
            failed_urls = []

            async with __import__('aiohttp').ClientSession() as http_session:
                for record in result:
                    product_id = record[0]
                    title = record[1]
                    images_data = record[2]

                    if isinstance(images_data, str):
                        try:
                            images_data = json.loads(images_data)
                        except:
                            images_data = [images_data]

                    for img_url in images_data[:1]:  # Test first image only
                        try:
                            async with http_session.head(img_url, timeout=5) as response:
                                if response.status == 200:
                                    content_type = response.headers.get('content-type', '')
                                    if 'image/' in content_type:
                                        successful_urls.append({
                                            'product_id': product_id,
                                            'title': title[:50] + '...' if len(title) > 50 else title,
                                            'url': img_url,
                                            'content_type': content_type
                                        })
                                        logger.debug(f"OK {img_url.split('/')[-1]} -> {content_type}")
                                    else:
                                        failed_urls.append({
                                            'product_id': product_id,
                                            'url': img_url,
                                            'reason': f'Not image: {content_type}'
                                        })
                                else:
                                    failed_urls.append({
                                        'product_id': product_id,
                                        'url': img_url,
                                        'reason': f'HTTP {response.status}'
                                    })
                        except Exception as e:
                            failed_urls.append({
                                'product_id': product_id,
                                'url': img_url,
                                'reason': str(e)
                            })

            # Show sample of unique images found
            if successful_urls:
                logger.info(f"Found {len(successful_urls)} accessible products")
                logger.info("Sample unique images:")
                for i, url_info in enumerate(successful_urls[:5]):
                    filename = url_info['url'].split('/')[-1]
                    logger.info(f"   {i+1}. {url_info['product_id']}: {filename}")

            return successful_urls, failed_urls

    except Exception as e:
        logger.error(f"Product fetching failed: {e}")
        return [], []

async def process_unique_batch(skip_count: int = 0, batch_size: int = 512):
    """Process a batch with unique products using pagination"""
    logger.info(f"Starting batch processing (skip={skip_count:,}, size={batch_size})")

    # Get unique products for this batch
    successful_urls, failed_urls = await get_unique_products_batch(skip_count, batch_size)

    if not successful_urls:
        logger.error("No accessible URLs found for this batch")
        return False

    try:
        sys.path.append('/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')

        # Import processing functions
        from run_fashionsig_precomputation import (
            setup_fashionsig,
            setup_qdrant,
            process_products_fashionsig
        )

        # Load model and setup (once per batch)
        logger.info("Loading FashionSigLIP model...")
        processor, model, device, torch, np = setup_fashionsig()
        if model is None:
            logger.error("Failed to load FashionSigLIP model")
            return False

        # Setup Qdrant
        qdrant_client, VectorParams, Distance = setup_qdrant()
        if qdrant_client is None:
            logger.error("Failed to setup Qdrant client")
            return False

        collection_name = "fashion_fashionsig_768d"

        # Convert URL info to product format
        products_to_process = []
        for url_info in successful_urls:
            product = {
                'id': url_info['product_id'],
                'title': url_info['title'],
                'description': '',  # No description available
                'images': [url_info['url']]
            }
            products_to_process.append(product)

        logger.info(f"Processing batch of {len(products_to_process)} products...")

        # Process the batch
        results = await process_products_fashionsig(
            products=products_to_process,
            processor=processor,
            model=model,
            device=device,
            torch=torch,
            np=np,
            qdrant_client=qdrant_client,
            collection_name=collection_name
        )

        batch_results = [r for r in results if r.get('status') == 'success']
        logger.info(f"Batch Results: {len(batch_results)} successful out of {len(products_to_process)} attempted")

        return len(batch_results) > 0

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_multiple_unique_batches(total_batches: int = 3, batch_size: int = 512):
    """Run multiple batches with unique products"""
    logger.info(f"Starting multi-batch processing: {total_batches} batches of {batch_size} products each")

    total_processed = 0
    successful_batches = 0

    for batch_num in range(1, total_batches + 1):
        skip_count = (batch_num - 1) * batch_size
        logger.info(f"{'='*60}")
        logger.info(f"BATCH {batch_num}/{total_batches} (products {skip_count:,} to {skip_count + batch_size:,})")
        logger.info(f"{'='*60}")

        success = await process_unique_batch(skip_count, batch_size)

        if success:
            successful_batches += 1
            total_processed += batch_size
            logger.info(f"Batch {batch_num} completed successfully")
        else:
            logger.error(f"Batch {batch_num} failed")

        # Progress summary
        logger.info(f"Progress: {successful_batches}/{batch_num} batches successful, {total_processed:,} products processed")

        # Small delay between batches
        if batch_num < total_batches:
            logger.info("2-second delay before next batch...")
            await asyncio.sleep(2)

    # Final summary
    logger.info(f"MULTI-BATCH SUMMARY:")
    logger.info(f"   Total batches: {total_batches}")
    logger.info(f"   Successful batches: {successful_batches}")
    logger.info(f"   Products processed: {total_processed:,}")
    logger.info(f"   Success rate: {successful_batches/total_batches*100:.1f}%")

    return successful_batches > 0

async def main():
    """Main function with different run modes"""

    # Configuration
    mode = os.getenv('MODE', 'single')  # 'single' or 'multi'
    batch_size = int(os.getenv('BATCH_SIZE', '512'))

    if mode == 'multi':
        total_batches = int(os.getenv('TOTAL_BATCHES', '3'))
        success = await run_multiple_unique_batches(total_batches, batch_size)
    else:
        # Single batch mode
        skip_count = int(os.getenv('SKIP_COUNT', '0'))
        success = await process_unique_batch(skip_count, batch_size)

    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)